import os
import sqlite3
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

CONFIG_FILE = "config.json"
LOG_FILE = "servicebox.log"

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
            "viewer_token": "VIEWER_ONLY_TOKEN"
        }
    
    with open(CONFIG_FILE, 'r') as f:
        config_data = json.load(f)
        
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


def setup_logging(level_name="INFO"):
    """Configures logging to both console and file with rotation."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    
    logger = logging.getLogger("ServiceBox")
    logger.setLevel(level)
    
    # Check if handlers are already added to avoid duplicates
    if not logger.handlers:
        # File Handler (Rotating: 5MB size, max 3 backups)
        file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(message)s') # Simpler for console
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
    return logger

# Singleton config instance
config = load_config()
logger = setup_logging(config.get("log_level", "INFO"))
