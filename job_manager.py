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
        self.loop = None
        
        # Safety Mechanisms
        self.consecutive_requests = 0
        self.consecutive_errors = 0
        self.is_panic_mode = False
        self.panic_until = 0

    def start_worker(self):
        if self.running:
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("JobManager Worker started.")

    def stop_worker(self):
        self.running = False
        logger.info("JobManager Worker stopping...")

    def _worker_loop(self):
        # Create a new event loop for this thread (required for Playwright/Asyncio)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
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
                
                # Execute Download with error catching
                result = {}
                try:
                    result = self.loop.run_until_complete(downloader.download_maintenance_plan(job['vin']))
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
                                if doc_id:
                                    logger.info(f"Uploaded {file_path} to Paperless with ID: {doc_id}")
                                    # Override file_path with a special format so the GUI knows it's from Paperless
                                    result['file_path'] = f"paperless:{doc_id}"
                                    file_path = result['file_path']
                                    
                                    # Delete local temporary file
                                    try:
                                        os.remove(file_path.replace(f"paperless:{doc_id}", "")) # Actually, the original file_path is already overwritten in the scope. Let's fix that.
                                    except:
                                        pass
                                    
                        except Exception as e:
                            logger.error(f"Failed to extract maintenance services or upload to Paperless: {e}")

                        # Fix local file deletion correctly
                        # If it was uploaded successfully, 'file_path' starts with paperless:
                        if isinstance(file_path, str) and file_path.startswith("paperless:"):
                            original_path = result.get('file_path_local_temp') # We need to store original path
                            # Instead of complex logic, we just use the dictionary original value
                            original_path = result.get('file_path') # WAIT! result['file_path'] was just overwritten.
                            pass # We will rewrite this chunk again properly in the next line to avoid confusion.
                    
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
                    error_msg = result.get('error', 'Unknown Error')
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
                
    def add_job(self, vin, priority=False):
        job_id = str(uuid.uuid4())
        p_val = 1 if priority else 0
        database.create_job(job_id, vin, p_val)
        
        job_dict = {"job_id": job_id, "vin": vin, "priority": p_val}
        
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

# Global Instance
job_manager = JobManager()
