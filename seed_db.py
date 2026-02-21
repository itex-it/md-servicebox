import sqlite3
import json
import time
import datetime
from database import DB_FILE

def seed_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Clear existing for clean test
    c.execute("DELETE FROM vehicle_history")
    
    print("Seeding rich dummy data...")
    
    # Helper for dates
    def get_date(offset_days=0):
        dt = datetime.datetime.now() + datetime.timedelta(days=offset_days)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def get_warranty_date(offset_years=0):
        dt = datetime.datetime.now() + datetime.timedelta(days=365*offset_years)
        return dt.strftime("%d/%m/%Y")

    examples = [
        {
            "vin": "VF3SUCCESS_CLEAN",
            "status": "Success",
            "timestamp": get_date(0),
            "file_path": "C:\\Downloads\\Clean.pdf",
            "warranty": {"Garantieende": get_warranty_date(2), "Amtl. Kennzeichen": "M-AB 1234"}, # Valid 2 years
            "recalls": {"status": "None", "message": "Keine Aktionen"},
            "lcdv": {"Engine": "V8 Turbo"}
        },
        {
            "vin": "VF7RECALL_ACTIVE",
            "status": "Success",
            "timestamp": get_date(-1),
            "file_path": "C:\\Downloads\\Recall.pdf",
            "warranty": {"Garantieende": get_warranty_date(1), "Kennzeichen": "B-XY 987"},
            "recalls": {"status": "Active", "message": "Rückrufaktion Bremsen"},
            "lcdv": {"Engine": "Electric"}
        },
        {
            "vin": "W0VWARRANTY_EXP", # Opel VIN
            "status": "Success",
            "timestamp": get_date(-2),
            "file_path": "C:\\Downloads\\Old.pdf",
            "warranty": {"Garantieende": get_warranty_date(-5), "Immatriculation": "HH-CC 555"}, # Expired 5 years ago
            "recalls": {"status": "None", "message": "Keine Aktionen"},
            "lcdv": {"Engine": "Diesel"}
        },
        {
            "vin": "VF7FAILURE_TIMEOUT",
            "status": "Failed",
            "timestamp": get_date(0),
            "file_path": None,
            "warranty": {},
            "recalls": {"status": "Unknown", "message": "Timeout during check"},
            "lcdv": {}
        }
    ]

    for ex in examples:
        c.execute("""
            INSERT INTO vehicle_history (vin, timestamp, status, file_path, warranty_data, lcdv_data, recall_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            ex["vin"], 
            ex["timestamp"], 
            ex["status"], 
            ex["file_path"], 
            json.dumps(ex["warranty"]), 
            json.dumps(ex["lcdv"]), 
            json.dumps(ex["recalls"]) # Note: DB schema might expect string for recall_message, but usually we store JSON in text
        ))
    
    # Update stats
    conn.commit()
    print("Data seeded.")
    conn.close()

if __name__ == "__main__":
    seed_data()
