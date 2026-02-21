import sqlite3
import json
import os
from datetime import datetime

DB_FILE = "servicebox_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vin TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT,
            warranty_data TEXT,  -- JSON string
            lcdv_data TEXT,      -- JSON string
            recall_status TEXT,
            recall_message TEXT,
            status TEXT DEFAULT 'Success', -- New column for extraction status (Success, Failed)
            recall_data TEXT     -- JSON string for full recall details
        )
    ''')

    # Status State Table (Latest snapshot per VIN)
    c.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            vin TEXT PRIMARY KEY,
            last_updated DATETIME,
            file_path TEXT,
            warranty_data TEXT,
            lcdv_data TEXT,
            recall_status TEXT,
            recall_message TEXT,
            recall_data TEXT,
            status TEXT
        )
    ''')
    
    # Jobs Table (Persistent Queue)
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            vin TEXT NOT NULL,
            status TEXT DEFAULT 'queued',   -- queued, processing, success, error
            priority INTEGER DEFAULT 0,     -- 1=High, 0=Normal
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            result TEXT,                    -- JSON result data
            error_message TEXT,
            retry_count INTEGER DEFAULT 0
        )
    ''')

    # Migration: Check if status column exists, if not add it
    try:
        c.execute("SELECT status FROM vehicle_history LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE vehicle_history ADD COLUMN status TEXT DEFAULT 'Success'")

    # Migration: Check if recall_data column exists
    try:
        c.execute("SELECT recall_data FROM vehicle_history LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE vehicle_history ADD COLUMN recall_data TEXT")
        
    conn.commit()
    conn.close()

def save_extraction(vin, file_path, vehicle_data, status='Success'):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    warranty_obj = vehicle_data.get('warranty') or vehicle_data.get('warranty_details') or {}
    warranty = json.dumps(warranty_obj)
    lcdv = json.dumps(vehicle_data.get('lcdv', {}))
    recalls = vehicle_data.get('recalls', {})
    recall_status = recalls.get('status', 'Unknown')
    recall_message = recalls.get('message', '')
    recall_data = json.dumps(recalls)
    
    print(f"[DB] Saving - VIN: {vin}, Warranty Keys: {list(warranty_obj.keys())}, Recalls: {len(recalls.get('details', []))} items") # Debug

    c.execute('''
        INSERT INTO vehicle_history (vin, file_path, warranty_data, lcdv_data, recall_status, recall_message, status, recall_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (vin, file_path, warranty, lcdv, recall_status, recall_message, status, recall_data))
    
    # Upsert into vehicles table
    c.execute('''
        INSERT OR REPLACE INTO vehicles (vin, last_updated, file_path, warranty_data, lcdv_data, recall_status, recall_message, recall_data, status)
        VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?)
    ''', (vin, file_path, warranty, lcdv, recall_status, recall_message, recall_data, status))
    
    conn.commit()
    conn.close()

def get_latest_vehicle(vin):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM vehicles WHERE vin = ?", (vin,))
    row = c.fetchone()
    conn.close()
    if row:
        item = dict(row)
        try: item['warranty_data'] = json.loads(item['warranty_data'])
        except: pass
        try: item['lcdv_data'] = json.loads(item['lcdv_data'])
        except: pass
        try: item['recalls_data'] = json.loads(item['recall_data']) if item['recall_data'] else {}
        except: pass
        return item
    return None

def create_job(job_id, vin, priority=0):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO jobs (job_id, vin, priority, status)
        VALUES (?, ?, ?, 'queued')
    ''', (job_id, vin, priority))
    conn.commit()
    conn.close()

def get_job(job_id):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_job_status(job_id, status, result=None, error_message=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    update_fields = ["status = ?, updated_at = datetime('now')"]
    params = [status]
    
    if result:
        update_fields.append("result = ?")
        params.append(json.dumps(result) if isinstance(result, dict) else result)
    
    if error_message:
        update_fields.append("error_message = ?")
        params.append(error_message)
        
    params.append(job_id)
    
    query = f"UPDATE jobs SET {', '.join(update_fields)} WHERE job_id = ?"
    c.execute(query, params)
    conn.commit()
    conn.close()

def get_next_queued_job():
    # Priority desc, then oldest created
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE status = 'queued' ORDER BY priority DESC, created_at ASC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_jobs(status=None, vin=None, limit=50):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = "SELECT * FROM jobs"
    params = []
    conditions = []
    
    if status:
        conditions.append("status = ?")
        params.append(status)
    if vin:
        conditions.append("vin LIKE ?")
        params.append(f"%{vin}%")
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, tuple(params))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_job(job_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count

def reset_job(job_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE jobs SET status = 'queued', created_at = datetime('now'), error_message = NULL WHERE job_id = ?", (job_id,))
    count = c.rowcount
    conn.commit()
    conn.close()
    return count

def get_history(vin=None, search_term=None, limit=100):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = "SELECT * FROM vehicle_history"
    params = []
    conditions = []
    
    if vin:
        conditions.append("vin = ?")
        params.append(vin)
    elif search_term:
        conditions.append("(vin LIKE ? OR recall_message LIKE ?)")
        params.extend([f"%{search_term}%", f"%{search_term}%"])
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, tuple(params))
    rows = c.fetchall()
    
    history = []
    for row in rows:
        item = dict(row)
        try: item['warranty_data'] = json.loads(item['warranty_data'])
        except: pass
        try: item['lcdv_data'] = json.loads(item['lcdv_data'])
        except: pass
        try: 
            if item['recall_data']:
                item['recalls_data'] = json.loads(item['recall_data'])
            else:
                # Fallback for old rows without recall_data
                item['recalls_data'] = {
                    'status': item['recall_status'],
                    'message': item['recall_message'],
                    'details': [] 
                }
        except Exception as e: 
            print(f"[DB] Error loading recall_data for {item['vin']}: {e}")
            item['recalls_data'] = {}
            
        history.append(item)
        
    conn.close()
    return history

def get_stats(days=30):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Total Count
    c.execute("SELECT COUNT(*) FROM vehicle_history")
    total = c.fetchone()[0]
    
    # Success/Fail (based on file_path presence or recall status)
    # Simplified: Assuming all entries are "processed". 
    # Real success tracking might need a 'status' column, but presence implies success.
    
    # Last Active
    c.execute("SELECT timestamp FROM vehicle_history ORDER BY timestamp DESC LIMIT 1")
    last_active = c.fetchone()
    last_active = last_active[0] if last_active else "Never"
    
    # Queue Stats
    c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")
    queue_counts = dict(c.fetchall())
    
    conn.close()
    return {
        "total_downloads": total,
        "last_active": last_active,
        "success_rate": 100, # Placeholder until we track failures in DB
        "queue": {
            "queued": queue_counts.get("queued", 0),
            "processing": queue_counts.get("processing", 0),
            "error": queue_counts.get("error", 0),
            "success": queue_counts.get("success", 0)
        }
    }
