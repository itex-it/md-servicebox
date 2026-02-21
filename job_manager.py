import asyncio
import uuid
import threading
import time
import database
from servicebox_downloader import ServiceBoxDownloader
from config_loader import logger

class JobManager:
    def __init__(self):
        self.downloader = ServiceBoxDownloader()
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

                # 3. Get Next Job
                job = database.get_next_queued_job()
                if not job:
                    time.sleep(2) # Idle wait
                    continue

                # 4. Process Job
                logger.info(f"Processing Job {job['job_id']} (VIN: {job['vin']})")
                
                # Mark as processing
                database.update_job_status(job['job_id'], 'processing')
                
                # Execute Download
                result = self.loop.run_until_complete(self.downloader.download_maintenance_plan(job['vin']))
                
                if result['success']:
                    database.update_job_status(job['job_id'], 'success', result=result)
                    
                    # Save to history/stats
                    try:
                        database.save_extraction(
                            job['vin'],
                            result.get('file_path'),
                            result.get('vehicle_data', {})
                        )
                    except Exception as e:
                        logger.error(f"Failed to save history for job {job['job_id']}: {e}")

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
        return job_id

    def get_status(self, job_id):
        return database.get_job(job_id)
        
    def retry_failed(self):
        # Implementation to reset 'error' jobs to 'queued'
        conn = database.sqlite3.connect(database.DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE jobs SET status = 'queued', created_at = datetime('now') WHERE status = 'error'")
        count = c.rowcount
        conn.commit()
        conn.close()
        return count

    def clear_queue(self):
        conn = database.sqlite3.connect(database.DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM jobs WHERE status = 'queued'")
        count = c.rowcount
        conn.commit()
        conn.close()
        return count

    def get_all_jobs(self, status=None, vin=None, limit=50):
        return database.get_jobs(status, vin, limit)

    def delete_job(self, job_id):
        return database.delete_job(job_id)

    def retry_job(self, job_id):
        return database.reset_job(job_id)

# Global Instance
job_manager = JobManager()
