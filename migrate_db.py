import database
from sqlalchemy import text

def run_migration():
    print(f"Running migration on {database.engine.url}...")
    try:
        with database.engine.begin() as conn:
            if "postgres" in str(database.engine.url):
                conn.execute(text("ALTER TABLE jobs ADD COLUMN recalls_only BOOLEAN DEFAULT FALSE;"))
            else:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN recalls_only BOOLEAN DEFAULT 0;"))
            print("Column 'recalls_only' added successfully.")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower() or "has no column" in str(e).lower():
            print("Column 'recalls_only' already exists.")
        else:
            print(f"Database Error during migration (recalls_only): {e}")

    try:
        with database.engine.begin() as conn:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN progress_message TEXT DEFAULT '';"))
            print("Column 'progress_message' added successfully.")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower() or "has no column" in str(e).lower():
            print("Column 'progress_message' already exists.")
        else:
            print(f"Database Error during migration (progress_message): {e}")

    try:
        with database.engine.begin() as conn:
            conn.execute(text("ALTER TABLE vehicles ADD COLUMN energy_type TEXT;"))
            print("Column 'energy_type' added successfully to vehicles.")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower() or "has no column" in str(e).lower():
            print("Column 'energy_type' already exists in vehicles.")
        else:
            print(f"Database Error during migration (energy_type vehicles): {e}")

    try:
        with database.engine.begin() as conn:
            conn.execute(text("ALTER TABLE vehicle_history ADD COLUMN energy_type TEXT;"))
            print("Column 'energy_type' added successfully to vehicle_history.")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower() or "has no column" in str(e).lower():
            print("Column 'energy_type' already exists in vehicle_history.")
        else:
            print(f"Database Error during migration (energy_type vehicle_history): {e}")

    # Initialize all other tables explicitly
    database.init_db()

if __name__ == "__main__":
    run_migration()
