import argparse
import json
import sys
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, VehicleHistory, Vehicle, Job, MaintenanceService
from config_loader import logger

# Initialize tables if they don't exist
Base.metadata.create_all(bind=engine)

def custom_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def export_data(filename="backup.json"):
    logger.info(f"Exporting database to {filename}...")
    db: Session = SessionLocal()
    try:
        data = {
            "vehicles": [v.__dict__ for v in db.query(Vehicle).all()],
            "history": [h.__dict__ for h in db.query(VehicleHistory).all()],
            "jobs": [j.__dict__ for j in db.query(Job).all()],
            "maintenance": [m.__dict__ for m in db.query(MaintenanceService).all()]
        }
        
        # Remove SQLAlchemy internal state
        for group in data.values():
            for row in group:
                row.pop('_sa_instance_state', None)
                
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=custom_serializer, indent=4)
            
        logger.info(f"Export complete. Saved {len(data['vehicles'])} vehicles, {len(data['history'])} history, {len(data['jobs'])} jobs, {len(data['maintenance'])} services.")
    except Exception as e:
        logger.error(f"Export failed: {e}")
    finally:
        db.close()

def import_data(filename="backup.json"):
    logger.info(f"Importing database from {filename}...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        db: Session = SessionLocal()
        try:
            # Helper to parse datetime strings
            def parse_dt(row, keys):
                for k in keys:
                    if row.get(k):
                        row[k] = datetime.fromisoformat(row[k])
                        
            # Import Vehicles
            if "vehicles" in data:
                for row in data["vehicles"]:
                    parse_dt(row, ['last_updated'])
                    existing = db.query(Vehicle).filter(Vehicle.vin == row['vin']).first()
                    if not existing:
                        db.add(Vehicle(**row))
            
            # Import History
            if "history" in data:
                for row in data["history"]:
                    parse_dt(row, ['timestamp'])
                    existing = db.query(VehicleHistory).filter(VehicleHistory.id == row['id']).first()
                    if not existing:
                        # id can be stripped to let autoincrement rule over if preferred
                        row.pop('id', None)
                        db.add(VehicleHistory(**row))
                        
            # Import Jobs
            if "jobs" in data:
                for row in data["jobs"]:
                    parse_dt(row, ['created_at', 'updated_at'])
                    existing = db.query(Job).filter(Job.job_id == row['job_id']).first()
                    if not existing:
                        db.add(Job(**row))
                        
            # Import Maintenance
            if "maintenance" in data:
                for row in data["maintenance"]:
                    existing = db.query(MaintenanceService).filter(MaintenanceService.id == row['id']).first()
                    if not existing:
                        row.pop('id', None)
                        db.add(MaintenanceService(**row))
                        
            db.commit()
            logger.info("Import complete.")
        except Exception as e:
            db.rollback()
            logger.error(f"Import failed during DB insertion: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to read file {filename}: {e}")

def delete_data(target):
    db: Session = SessionLocal()
    try:
        count = 0
        if target in ["queue", "jobs", "all"]:
            count += db.query(Job).delete()
            logger.info("Cleared jobs table.")
            
        if target in ["history", "all"]:
            count += db.query(VehicleHistory).delete()
            count += db.query(Vehicle).delete()
            logger.info("Cleared history and vehicles tables.")
            
        if target in ["maintenance", "all"]:
            count += db.query(MaintenanceService).delete()
            logger.info("Cleared maintenance services table.")
            
        db.commit()
        logger.info(f"Delete operation for target '{target}' complete. Affected {count} rows.")
    except Exception as e:
        db.rollback()
        logger.error(f"Delete failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ServiceBox Database Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Export
    p_export = subparsers.add_parser("export", help="Export DB to JSON")
    p_export.add_argument("--file", default="backup.json", help="Output filename")
    
    # Import
    p_import = subparsers.add_parser("import", help="Import DB from JSON")
    p_import.add_argument("--file", default="backup.json", help="Input filename")
    
    # Delete
    p_clear = subparsers.add_parser("clear", help="Clear specific DB tables")
    p_clear.add_argument("--target", choices=["queue", "history", "maintenance", "all"], required=True, help="Target data to clear")
    
    args = parser.parse_args()
    
    if args.command == "export":
        export_data(args.file)
    elif args.command == "import":
        import_data(args.file)
    elif args.command == "clear":
        confirm = input(f"Are you sure you want to clear target '{args.target}'? This cannot be undone! (y/N): ")
        if confirm.lower() == 'y':
            delete_data(args.target)
        else:
            print("Aborted.")
