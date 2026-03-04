import sqlite3
import shutil
import os
import glob
from datetime import datetime
import logging
import time

# Basic logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_SOURCE = "/app/data/servicebox_history.db"
BACKUP_DIR = "/app/backups"
RETENTION_DAYS = 14

def create_safe_backup():
    if not os.path.exists(DB_SOURCE):
        logger.warning(f"Source DB {DB_SOURCE} not found. Nothing to backup.")
        return False

    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_DIR, f"servicebox_history_{timestamp}.db")
    
    logger.info(f"Starting safe SQLite backup from {DB_SOURCE} to {backup_file}")
    
    try:
        # We use the built-in SQLite backup API for a locked, transaction-safe snapshot
        source_con = sqlite3.connect(DB_SOURCE)
        dest_con = sqlite3.connect(backup_file)
        
        with source_con:
            source_con.backup(dest_con)
            
        dest_con.close()
        source_con.close()
        
        file_size = os.path.getsize(backup_file) / (1024 * 1024)
        logger.info(f"Backup successful: {backup_file} ({file_size:.2f} MB)")
        
        cleanup_old_backups()
        return True
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        # In case of catastrophic failure, delete the broken/partial backup
        if os.path.exists(backup_file):
            try: os.remove(backup_file)
            except: pass
        return False

def cleanup_old_backups():
    cutoff = time.time() - (RETENTION_DAYS * 86400)
    
    backups = glob.glob(os.path.join(BACKUP_DIR, "*.db"))
    for file in backups:
        if os.path.getctime(file) < cutoff:
            try:
                os.remove(file)
                logger.info(f"Deleted old backup: {file}")
            except Exception as e:
                logger.error(f"Failed to delete old backup {file}: {e}")

if __name__ == "__main__":
    logger.info("ServiceBox Backup Manager Started.")
    create_safe_backup()
