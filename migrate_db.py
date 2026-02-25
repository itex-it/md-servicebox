import sqlite3
import os

db_path = "servicebox_history.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE jobs ADD COLUMN recalls_only BOOLEAN DEFAULT 0;")
    print("Column added successfully.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("Column already exists.")
    else:
        print(f"Database Error: {e}")

conn.commit()
conn.close()
