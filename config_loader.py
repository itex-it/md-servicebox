import json
import os
import logging
from logging.handlers import RotatingFileHandler

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
            "output_dir": "downloads"
        }
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

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
