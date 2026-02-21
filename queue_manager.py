import json
import redis
from config_loader import config, logger

class QueueManager:
    """
    Handles background extraction jobs using Redis for real-time queueing.
    We maintain a List 'servicebox:jobs:queue' for pending jobs.
    """
    def __init__(self):
        self.redis_url = config.get("redis_url", "redis://localhost:6379/0")
        self.enabled = False
        self.client = None
        self._queue_key = "servicebox:jobs:queue"
        
        try:
            self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
            self.enabled = True
            logger.info(f"[QueueManager] Successfully connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"[QueueManager] Failed to connect to Redis. Falling back to SQL polling mode. Error: {e}")
            self.enabled = False

    def push_job(self, job_dict: dict, priority: int = 0):
        """
        Pushes a job onto the Redis queue.
        If priority is high, push to left (LPOP first), else push to right (RPOP last).
        For simplicity with BLPOP, we push high priority to the right and use RPOP? 
        Actually, we can maintain two queues if needed, but for now we push left for high priority and right for normal.
        Wait, BLPOP pops from Left. So:
        High Priority -> LPUSH
        Normal Priority -> RPUSH
        """
        if not self.enabled:
            return False
            
        payload = json.dumps(job_dict)
        try:
            if priority > 0:
                self.client.lpush(self._queue_key, payload)
            else:
                self.client.rpush(self._queue_key, payload)
            return True
        except Exception as e:
            logger.error(f"[QueueManager] Redis Push Error: {e}")
            return False

    def wait_next_job(self, timeout=0):
        """
        Blocks until a job is available in the queue (or timeout reached).
        Returns the parsed job dict or None.
        """
        if not self.enabled:
            return None
            
        try:
            # BLPOP blocks and returns (queue_name, payload)
            result = self.client.blpop(self._queue_key, timeout=timeout)
            if result:
                _, payload = result
                return json.loads(payload)
            return None
        except Exception as e:
            logger.error(f"[QueueManager] Redis Pop Error: {e}")
            return None

    def clear_queue(self):
        if self.enabled:
            self.client.delete(self._queue_key)

# Global Instance
queue_manager = QueueManager()
