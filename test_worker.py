import asyncio
from config_loader import logger
from database import init_db
from job_manager import job_manager
import time

init_db()

# Add a job
job_id = job_manager.add_job("VF7NT9HXYMY0066", priority=True)
print(f"Added Job {job_id}. Starting worker...")

job_manager.start_worker()

for i in range(15):
    print(f"Waiting... {i}")
    time.sleep(1)
