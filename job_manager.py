import asyncio
import uuid
import threading
import time
import os
import database
from downloader_factory import DownloaderFactory
import pdf_parser
from config_loader import logger
from paperless_client import paperless_client
from queue_manager import queue_manager

class JobManager:
    def __init__(self):
        self.running = False
        self.worker_thread = None
        
        # Safety Mechanisms
        self.consecutive_requests = 0
        self.consecutive_errors = 0
        self.is_panic_mode = False
        self.panic_until = 0

    def start_worker(self):
        if self.running:
            return
            
        # Clear left-over queues on startup 
        database.cleanup_stuck_jobs()
        if queue_manager.enabled:
            queue_manager.clear_queue()
            
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        self.gc_thread = threading.Thread(target=self._garbage_collection_loop, daemon=True)
        self.gc_thread.start()
        logger.info("JobManager Worker started.")

    def stop_worker(self):
        self.running = False
        logger.info("JobManager Worker stopping...")

    def _worker_loop(self):
        # Each download job gets a completely fresh, isolated asyncio event loop
        # via asyncio.run(). Do NOT create a shared loop here — on Linux/Docker,
        # a global loop persists across iterations and corrupts Playwright's driver.
        while self.running:
            try:
                # 1. Check Panic Mode
                if self.is_panic_mode:
                    if time.time() > self.panic_until:
                        logger.info("Panic Mode ended. Resuming...")
                        self.is_panic_mode = False
                        self.consecutive_errors = 0
                    else:
                        time.sleep(5)
                        continue

                # 2. Check Cool-down
                if self.consecutive_requests >= 10:
                    logger.info("Cool-down: Pausing for 60s...")
                    time.sleep(60)
                    self.consecutive_requests = 0

                # 3. Get Next Job from Redis Queue (Blocking for 5 seconds)
                if queue_manager.enabled:
                    job = queue_manager.wait_next_job(timeout=5)
                else:
                    # Fallback to DB Polling if Redis is down
                    job = database.get_next_queued_job()
                    if not job:
                        time.sleep(2)
                        
                if not job:
                    continue  # Timeout reached, loop again

                # 4. Process Job
                logger.info(f"Processing Job {job['job_id']} (VIN: {job['vin']})")
                
                # Mark as processing
                database.update_job_status(job['job_id'], 'processing')
                
                # Dynamic Routing based on Brand (WMI)
                downloader = DownloaderFactory.get_downloader(job['vin'])
                
                def progress_cb(msg):
                    try:
                        database.update_job_progress(job['job_id'], msg)
                    except Exception as e:
                        pass # Non-critical failure
                
                # Execute Download with error catching
                result = {}
                try:
                    recalls_only = job.get('recalls_only', False)
                    
                    # Create a completely fresh event loop strictly for this download to avoid dirty state Driver crashes
                    async def isolated_run():
                        return await downloader.download_maintenance_plan(job['vin'], recalls_only=recalls_only, progress_callback=progress_cb)
                        
                    result = asyncio.run(isolated_run())
                    
                except Exception as eval_err:
                    logger.error(f"Playwright/Downloader Engine Error for VIN {job['vin']}: {eval_err}")
                    result = {"success": False, "error": str(eval_err)}
                
                if result.get('success', False):
                    file_path = result.get('file_path')
                    
                    # Extract and save maintenance services if PDF was downloaded
                    if file_path:
                        try:
                            services = pdf_parser.extract_maintenance_services(file_path)
                            if services:
                                result['maintenance_services_count'] = len(services)
                                database.save_maintenance_services(job['vin'], services)
                                
                            # Upload to Paperless if enabled
                            if paperless_client.enabled:
                                title = f"Wartungsplan {job['vin']}"
                                tags = ["ServiceBox", "Wartungsplan", job['vin']]
                                
                                doc_id = paperless_client.upload_document(file_path, title, tags=tags)
                                if doc_id == "OFFLINE":
                                    logger.warning(f"Paperless is OFFLINE. Caching {file_path} locally for later sync.")
                                    # We don't change file_path, so it stays as the local path and is NOT deleted.
                                elif doc_id:
                                    logger.info(f"Uploaded {file_path} to Paperless with ID: {doc_id}")
                                    # Override file_path with a special format so the GUI knows it's from Paperless
                                    result['file_path'] = f"paperless:{doc_id}"
                                    file_path = result['file_path']
                                    
                                    # Delete local temporary file
                                    try:
                                        # result['file_path'] is paperless:XYZ, but original file_path is still available locally
                                        pass 
                                    except:
                                        pass
                                    
                        except Exception as e:
                            logger.error(f"Failed to extract maintenance services or upload to Paperless: {e}")

                        # Fix local file deletion correctly
                        # Original local path is stored in result object initially before overriding
                        local_path = result.get('file_path')
                        if local_path and result.get('file_path') != local_path and str(result.get('file_path', '')).startswith('paperless:'):
                             try:
                                 os.remove(local_path)
                             except BaseException as fallback_e:
                                 pass
                    
                    # Save to history/stats
                    try:
                        database.save_extraction(
                            job['vin'],
                            file_path,
                            result.get('vehicle_data', {})
                        )
                        database.update_job_status(job['job_id'], 'success', result)
                    except Exception as e:
                        logger.error(f"Failed to save history for job {job['job_id']}: {e}")
                        database.update_job_status(job['job_id'], 'error', error_message=str(e))

                    self.consecutive_requests += 1
                    self.consecutive_errors = 0 # Reset error count
                else:
                    error_msg = result.get('message') or result.get('error') or 'Unknown Error'
                    database.update_job_status(job['job_id'], 'error', error_message=error_msg)
                    logger.error(f"Job {job['job_id']} Failed: {error_msg}")
                    
                    # Error Handling Strategy
                    self.consecutive_errors += 1
                    if "Access Denied" in error_msg or self.consecutive_errors >= 3:
                        logger.warning("Triggering PANIC MODE (15 min pause)")
                        self.is_panic_mode = True
                        self.panic_until = time.time() + (15 * 60)

                # Small pause between jobs to be nice
                time.sleep(2)

            except Exception as e:
                logger.error(f"Worker Loop Error: {e}")
                time.sleep(5)
                
    def add_job(self, vin, priority=False, recalls_only=False):
        # Idempotency check: if a job for this VIN is already queued or processing,
        # return the existing job ID instead of creating a duplicate.
        existing_jobs = database.get_jobs(vin=vin, status=None, limit=10)
        for job in existing_jobs:
            if job.get('status') in ('queued', 'processing'):
                logger.info(f"[JobManager] Dedup: Returning existing job {job['job_id']} for VIN {vin} (status={job['status']})")
                return job['job_id']

        job_id = str(uuid.uuid4())
        p_val = 1 if priority else 0
        database.create_job(job_id, vin, p_val)
        
        job_dict = {"job_id": job_id, "vin": vin, "priority": p_val, "recalls_only": recalls_only}
        
        if queue_manager.enabled:
            queue_manager.push_job(job_dict, priority=p_val)
            
        return job_id

    def get_status(self, job_id):
        return database.get_job(job_id)
        
    def retry_failed(self):
        # Implementation to reset 'error' jobs to 'queued'
        # With Redis, we need to push them back to the queue
        failed_jobs = database.get_jobs(status='error')
        count = 0
        for job in failed_jobs:
            self.retry_job(job['job_id'])
            count += 1
        return count

    def clear_queue(self):
        # Clear Database
        count = database.clear_queue(['queued', 'processing', 'error'])
        
        # Clear Redis
        if queue_manager.enabled:
            queue_manager.clear_queue()
        return count

    def get_all_jobs(self, status=None, vin=None, limit=50):
        return database.get_jobs(status, vin, limit)

    def delete_job(self, job_id):
        return database.delete_job(job_id)

    def delete_jobs(self, job_ids):
        # Chunking to prevent SQLite's maximum variable limit in IN clauses
        chunk_size = 900
        total_deleted = 0
        for i in range(0, len(job_ids), chunk_size):
            chunk = job_ids[i:i + chunk_size]
            total_deleted += database.delete_jobs(chunk)
            
        if queue_manager.enabled:
            # Note: Hard to sync selectively with Redis without a scan, 
            # simplest is to just let the worker drop them when popped if not in DB.
            pass
        return total_deleted

    def retry_job(self, job_id):
        job = database.get_job(job_id)
        if job:
            database.reset_job(job_id)
            if queue_manager.enabled:
                queue_manager.push_job(job, priority=job.get('priority', 0))
            return 1
        return 0

    def _garbage_collection_loop(self):
        """Runs periodically to clean up old files and sync offline Paperless PDFs."""
        logger.info("Garbage Collection & Paperless Sync thread started.")
        while self.running:
            try:
                # 1. Sync Offline PDFs to Paperless
                if paperless_client.enabled and os.path.exists("downloads"):
                    for filename in os.listdir("downloads"):
                        if filename.endswith(".pdf"):
                            file_path = os.path.join("downloads", filename)
                            # Parse VIN from filename (format: VIN_TIMESTAMP_Wartungsplan.pdf)
                            parts = filename.split("_")
                            if len(parts) >= 3:
                                vin = parts[0]
                                title = f"Wartungsplan {vin}"
                                tags = ["ServiceBox", "Wartungsplan", vin]
                                
                                logger.info(f"Syncing offline PDF found in downloads: {filename}")
                                doc_id = paperless_client.upload_document(file_path, title, tags=tags)
                                
                                if doc_id and doc_id != "OFFLINE":
                                    logger.info(f"Successfully synced {filename} to Paperless. Deleting local copy.")
                                    # Update Database History Record
                                    with database.SessionLocal() as db:
                                        from models import VehicleHistory, Vehicle
                                        db.query(VehicleHistory).filter(VehicleHistory.file_path == str(os.path.abspath(file_path))).update({"file_path": f"paperless:{doc_id}"})
                                        db.query(Vehicle).filter(Vehicle.file_path == str(os.path.abspath(file_path))).update({"file_path": f"paperless:{doc_id}"})
                                        db.commit()
                                    try: os.remove(file_path)
                                    except: pass

                # 2. Cleanup Old Debug Files (>3 Days)
                if os.path.exists("debug"):
                    now = time.time()
                    for filename in os.listdir("debug"):
                        filepath = os.path.join("debug", filename)
                        if os.path.getmtime(filepath) < now - (3 * 86400):
                            try: os.remove(filepath)
                            except: pass
                            
                # 3. Cleanup super old stranded PDFs (>30 days)
                if os.path.exists("downloads"):
                    now = time.time()
                    for filename in os.listdir("downloads"):
                         filepath = os.path.join("downloads", filename)
                         if os.path.getmtime(filepath) < now - (30 * 86400):
                             try: os.remove(filepath)
                             except: pass

            except Exception as e:
                logger.error(f"GC Thread Error: {e}")
                
            # Sleep for 15 minutes
            for _ in range(15 * 60):
                if not self.running: break
                time.sleep(1)

# Global Instance
job_manager = JobManager()
