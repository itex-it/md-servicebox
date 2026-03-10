import os
import sqlite3
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import zoneinfo
from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = "config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "servicebox.log")

# Ensure required directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)  # Ensure data directory exists for the database
os.makedirs("downloads", exist_ok=True)

def load_config():
    """Loads configuration from JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return {
            "user_id": "DEFAULT_USER",
            "password": "DEFAULT_PASSWORD",
            "login_url": "https://servicebox.peugeot.com/",
            "headless": False,
            "log_level": "INFO",
            "output_dir": "downloads",
            "auth_token": "SECRET_TOKEN_123",
            "viewer_token": "VIEWER_ONLY_TOKEN",
            "db_connection": "sqlite:///data/servicebox_history.db",
            "redis_url": "redis://redis:6379/0",
            "cache_hits": 0
        }
    
    with open(CONFIG_FILE, 'r') as f:
        config_data = json.load(f)
        if "cache_hits" not in config_data:
            config_data["cache_hits"] = 0
        
    # Docker / Environment Variable Overrides
    if os.getenv("REDIS_URL"):
        config_data["redis_url"] = os.getenv("REDIS_URL")
    if os.getenv("DB_CONNECTION"):
        config_data["db_connection"] = os.getenv("DB_CONNECTION")
        
    return config_data

def save_config(new_data: dict):
    """Saves the given config dictionary back to the JSON file, preserving existing keys where not overwritten."""
    global config
    
    # Load current from disk just in case
    current_disk_data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            try:
                current_disk_data = json.load(f)
            except Exception:
                pass
                
    # Update with new values
    for k, v in new_data.items():
        if k not in ["redis_url", "db_connection"]: # Don't persist environment overrides
            current_disk_data[k] = v
            config[k] = v # Update RAM instance
            
    # Write back
    with open(CONFIG_FILE, 'w') as f:
        json.dump(current_disk_data, f, indent=4)

def increment_cache_hits():
    """Increments the persistent cache_hits counter by 1."""
    global config
    hits = config.get("cache_hits", 0) + 1
    config["cache_hits"] = hits
    
    # Save only the hits quietly to disk without triggering a full re-save of all other vars
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
            data["cache_hits"] = hits
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to increment cache hits on disk: {e}")


def setup_logging(level_name="INFO"):
    """Configures logging to both console and file with rotation.
       Forces Europe/Vienna timezone for consistency.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    
    logger = logging.getLogger("ServiceBox")
    logger.setLevel(level)
    
    class ViennaFormatter(logging.Formatter):
        def converter(self, timestamp):
            dt = datetime.fromtimestamp(timestamp)
            vienna_tz = zoneinfo.ZoneInfo("Europe/Vienna")
            # Convert UTC/Local timestamp to Vienna timezone explicitly
            # Since fromtimestamp() usually creates a naive local time, we convert it properly
            dt_utc = datetime.fromtimestamp(timestamp, tz=zoneinfo.ZoneInfo("UTC"))
            return dt_utc.astimezone(vienna_tz).timetuple()
            
    # Check if handlers are already added to avoid duplicates
    if not logger.handlers:
        # File Handler (Rotating: 5MB size, max 3 backups)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        file_formatter = ViennaFormatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_formatter = ViennaFormatter('%(asctime)s - %(levelname)s - %(message)s') # Also add timestamp to console for debugging
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # Capture Uvicorn Logs into the same file so the Dashboard sees HTTP traffic
        uvicorn_access = logging.getLogger("uvicorn.access")
        
        # Filter out noisy endpoints from Uvicorn logs
        class EndpointFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                # Mute polling endpoints in logs
                return not any(val in record.getMessage() for val in ["/api/stats", "/api/logs", "/api/jobs", "/api/history?limit="])
                
        uvicorn_access.addFilter(EndpointFilter())
        uvicorn_access.addHandler(file_handler)
        
        uvicorn_error = logging.getLogger("uvicorn.error")
        uvicorn_error.addHandler(file_handler)
        
    return logger

# Singleton config instance
config = load_config()
logger = setup_logging(config.get("log_level", "INFO"))
