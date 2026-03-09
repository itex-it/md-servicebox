import json
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select, update, delete, func, desc, or_, text
from sqlalchemy.orm import sessionmaker
import config_loader

from models import Base, VehicleHistory, Vehicle, Job, MaintenanceService

CONFIG_FILE = "config/config.json"

def get_db_url():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Default to SQLite if missing
            return config.get('db_connection', 'sqlite:///data/servicebox_history.db')
    except Exception:
        return 'sqlite:///data/servicebox_history.db'

# Create engine, use connect_args for SQLite to avoid thread issues just in case
url = get_db_url()
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}

engine = create_engine(url, echo=False, connect_args=connect_args)

from sqlalchemy import event
if url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    print(f"[DB] Initializing database at {url}")
    Base.metadata.create_all(bind=engine)
    
    # Graceful migration for existing SQLite databases (adds the auto_refresh column if missing)
    if url.startswith("sqlite"):
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE vehicles ADD COLUMN auto_refresh BOOLEAN DEFAULT 1"))
                conn.commit()
                print("[DB] Migration: Added auto_refresh column to vehicles table.")
        except Exception as e:
            # Column likely already exists
            pass

def save_extraction(vin, file_path, vehicle_data, status='Success'):
    with SessionLocal() as db:
        warranty_obj = vehicle_data.get('warranty') or vehicle_data.get('warranty_details') or {}
        warranty = json.dumps(warranty_obj)
        lcdv_obj = vehicle_data.get('lcdv', {})
        lcdv = json.dumps(lcdv_obj)
        recalls = vehicle_data.get('recalls', {})
        recall_status = recalls.get('status', 'Unknown')
        recall_message = recalls.get('message', '')
        recall_data = json.dumps(recalls)
        
        # Insert History (always insert all data we got on this run)
        history_entry = VehicleHistory(
            vin=vin,
            file_path=file_path,
            warranty_data=warranty,
            lcdv_data=lcdv,
            recall_status=recall_status,
            recall_message=recall_message,
            status=status,
            recall_data=recall_data
        )
        db.add(history_entry)
        
        # Upsert Vehicle (merge, don't overwrite with empty)
        existing = db.query(Vehicle).filter(Vehicle.vin == vin).first()
        if existing:
            # Update
            existing.file_path = file_path
            
            # Merge logic for vehicle data: Only overwrite if new data isn't empty
            # If the current extraction failed to grab warranty/lcdv (empty string or '{}'), 
            # we keep the old valid data to prevent data loss.
            if warranty and warranty != "{}" and warranty != '""':
                existing.warranty_data = warranty
            if lcdv and lcdv != "{}" and lcdv != '""':
                existing.lcdv_data = lcdv
                
            existing.recall_status = recall_status
            existing.recall_message = recall_message
            existing.recall_data = recall_data
            existing.status = status
            existing.last_updated = datetime.now() # Manually trigger update
            # We explicitly do NOT touch existing.auto_refresh here to preserve user settings
        else:
            # Insert
            new_vehicle = Vehicle(
                vin=vin, file_path=file_path, warranty_data=warranty,
                lcdv_data=lcdv, recall_status=recall_status,
                recall_message=recall_message, status=status,
                recall_data=recall_data, auto_refresh=True
            )
            db.add(new_vehicle)
        db.commit()

def update_vehicle_settings(vin, auto_refresh: bool):
    with SessionLocal() as db:
        vehicle = db.query(Vehicle).filter(Vehicle.vin == vin).first()
        if vehicle:
            vehicle.auto_refresh = auto_refresh
            db.commit()
            return True
        return False    
        db.commit()

def get_latest_vehicle(vin):
    with SessionLocal() as db:
        vehicle = db.query(Vehicle).filter(Vehicle.vin == vin).first()
        if not vehicle:
            return None
        
        # Convert to dict manually to emulate old sqlite row behavior
        item = {
            'vin': vehicle.vin,
            'last_updated': str(vehicle.last_updated) if vehicle.last_updated else None,
            'file_path': vehicle.file_path,
            'status': vehicle.status,
            'warranty_data': {},
            'lcdv_data': {},
            'recalls_data': {}
        }
        
        try: item['warranty_data'] = json.loads(vehicle.warranty_data) if vehicle.warranty_data else {}
        except: pass
        try: item['lcdv_data'] = json.loads(vehicle.lcdv_data) if vehicle.lcdv_data else {}
        except: pass
        try:
            if vehicle.recall_data:
                item['recalls_data'] = json.loads(vehicle.recall_data)
            else:
                item['recalls_data'] = {
                    'status': vehicle.recall_status,
                    'message': vehicle.recall_message,
                    'details': []
                }
        except: pass
        return item

def create_job(job_id, vin, priority=0, recalls_only=False):
    with SessionLocal() as db:
        job = Job(job_id=job_id, vin=vin, status='queued', priority=priority, recalls_only=recalls_only)
        db.add(job)
        db.commit()

def get_job(job_id):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return None
        # Convert sqlalchemy object to dict, ignoring internal state
        d = dict(job.__dict__)
        d.pop('_sa_instance_state', None)
        if d.get('created_at'): d['created_at'] = str(d['created_at'])
        if d.get('updated_at'): d['updated_at'] = str(d['updated_at'])
        return d

def update_job_progress(job_id, message):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.progress_message = message
            job.updated_at = datetime.utcnow()
            db.commit()

def update_job_status(job_id, status, result=None, error_message=None):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.status = status
            job.updated_at = datetime.utcnow()
            if result:
                job.result = json.dumps(result) if isinstance(result, dict) else result
            if error_message:
                job.error_message = error_message
            db.commit()

def get_next_queued_job():
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.status == 'queued').order_by(Job.priority.desc(), Job.created_at.asc()).first()
        if not job:
            return None
        d = dict(job.__dict__)
        d.pop('_sa_instance_state', None)
        if d.get('created_at'): d['created_at'] = str(d['created_at'])
        if d.get('updated_at'): d['updated_at'] = str(d['updated_at'])
        return d

def get_jobs(status=None, vin=None, limit=50):
    with SessionLocal() as db:
        query = db.query(Job)
        if status:
            query = query.filter(Job.status == status)
        if vin:
            query = query.filter(Job.vin.like(f"%{vin}%"))
        jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
        
        res = []
        for j in jobs:
            d = dict(j.__dict__)
            d.pop('_sa_instance_state', None)
            if d.get('created_at'): d['created_at'] = str(d['created_at'])
            if d.get('updated_at'): d['updated_at'] = str(d['updated_at'])
            res.append(d)
        return res

def delete_job(job_id):
    with SessionLocal() as db:
        result = db.query(Job).filter(Job.job_id == job_id).delete()
        db.commit()
        return result

def delete_jobs(job_ids: list):
    if not job_ids: return 0
    with SessionLocal() as db:
        result = db.query(Job).filter(Job.job_id.in_(job_ids)).delete(synchronize_session=False)
        db.commit()
        return result

def reset_job(job_id):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.status = 'queued'
            job.created_at = datetime.utcnow()
            job.error_message = None
            db.commit()
            return 1
        return 0

def cleanup_stuck_jobs():
    """
    Called on startup to reset any jobs that were left in 'processing' 
    due to a sudden server shutdown or crash.
    """
    with SessionLocal() as db:
        stuck_jobs = db.query(Job).filter(Job.status.in_(['processing', 'queued'])).all()
        for job in stuck_jobs:
            job.status = 'error'
            job.error_message = 'Job cancelled due to server shutdown/restart.'
            job.updated_at = datetime.utcnow()
        if stuck_jobs:
            db.commit()
            print(f"[DB] Cleaned up {len(stuck_jobs)} stuck jobs.")
        return len(stuck_jobs)

def clear_queue(status_list=None):
    with SessionLocal() as db:
        query = db.query(Job)
        if status_list:
            query = query.filter(Job.status.in_(status_list))
        count = query.delete(synchronize_session=False)
        db.commit()
        return count

def get_open_recalls(brand=None):
    """
    Returns a list of all vehicles that have an open recall campaign.
    We assume an open recall is any status that is NOT 'Unknown', 'Keine Rückrufe', 'OK', etc.
    """
    with SessionLocal() as db:
        query = db.query(Vehicle).filter(
            Vehicle.recall_status.isnot(None),
            Vehicle.recall_status != '',
            Vehicle.recall_status != 'Unknown',
            Vehicle.recall_status.notilike('%Keine Rückrufaktionen%'),
            Vehicle.recall_status.notilike('%Keine Rückrufe%')
        )
        
        # Optional: We could filter by brand here if the VIN prefix matches, though it's easier 
        # to return them all and let the API filter if desired.
        rows = query.order_by(Vehicle.last_updated.desc()).all()
        
        recalls = []
        for row in rows:
            # Check the actual recall_data JSON to ensure there's a code and it's not resolved
            status_text = row.recall_status or ""
            message_text = row.recall_message or ""
            
            # Simple heuristic: If it has words like "OFFEN", "Sicherheit", or just a code without 'Keine'
            if "kein" not in status_text.lower() and "no recall" not in status_text.lower():
                recalls.append({
                    "vin": row.vin,
                    "recall_status": status_text,
                    "recall_message": message_text,
                    "last_updated": str(row.last_updated) if row.last_updated else None
                })
                
        return recalls

def search_vehicles(energy_type=None, min_age_years=None):
    """
    Finds vehicles in the local cache matching criteria like energy type or age.
    This inspects the JSON payload stored in warranty_data and lcdv_data.
    """
    with SessionLocal() as db:
        query = db.query(Vehicle)
        
        # We fetch all (or a large limit) and filter in Python since SQLite JSON extraction 
        # is complex and sometimes version-dependent, and the cache size (<10k) allows in-memory filtering.
        vehicles = query.all()
        results = []
        
        now = datetime.now()
        
        for v in vehicles:
            match = True
            
            # Extract JSON data safely
            try: warranty = json.loads(v.warranty_data) if v.warranty_data else {}
            except: warranty = {}
                
            try: lcdv = json.loads(v.lcdv_data) if v.lcdv_data else {}
            except: lcdv = {}
            
            # --- Check Energy Type ---
            if energy_type and match:
                # E.g. lcdv might have {"Energie": "ELEKTROMOTOR"}
                v_energy = str(lcdv.get("Energie", "")).upper()
                if energy_type.upper() not in v_energy:
                    match = False
                    
            # --- Check Age (from warranty start date) ---
            if min_age_years is not None and match:
                # Peugeot sometimes calls it "Startdatum der Garantie"
                start_date_str = warranty.get("Startdatum der Garantie") or warranty.get("warranty_start_date")
                
                v_age_years = 0
                if start_date_str:
                    try:
                        # Common format: "15.03.2018" or "2018-03-15"
                        if "." in start_date_str:
                            start_date = datetime.strptime(start_date_str, "%d.%m.%Y")
                        else:
                            start_date = datetime.strptime(start_date_str.split("T")[0], "%Y-%m-%d")
                        v_age_years = (now - start_date).days / 365.25
                    except:
                        pass
                
                if v_age_years < min_age_years:
                    match = False
                    
            if match:
                results.append({
                    "vin": v.vin,
                    "auto_refresh": getattr(v, "auto_refresh", True),
                    "energy": lcdv.get("Energie", "Unknown"),
                    "age_years": round(v_age_years, 1) if 'v_age_years' in locals() and v_age_years > 0 else None,
                    "last_updated": str(v.last_updated) if v.last_updated else None
                })
                
        return results

def get_history(vin=None, search_term=None, limit=100):
    with SessionLocal() as db:
        query = db.query(VehicleHistory)
        if vin:
            query = query.filter(VehicleHistory.vin == vin)
        elif search_term:
            query = query.filter(
                or_(
                    VehicleHistory.vin.like(f"%{search_term}%"),
                    VehicleHistory.recall_message.like(f"%{search_term}%")
                )
            )
            
        rows = query.order_by(VehicleHistory.timestamp.desc()).limit(limit).all()
        
        history = []
        for row in rows:
            item = dict(row.__dict__)
            item.pop('_sa_instance_state', None)
            
            # Format timestamp
            if item.get('timestamp'):
                item['timestamp'] = str(item['timestamp'])
                
            try: item['warranty_data'] = json.loads(item['warranty_data']) if item.get('warranty_data') else {}
            except: pass
            try: item['lcdv_data'] = json.loads(item['lcdv_data']) if item.get('lcdv_data') else {}
            except: pass
            try: 
                if item.get('recall_data'):
                    item['recalls_data'] = json.loads(item['recall_data'])
                else:
                    item['recalls_data'] = {
                        'status': item.get('recall_status'),
                        'message': item.get('recall_message'),
                        'details': [] 
                    }
            except Exception as e: 
                print(f"[DB] Error loading recall_data for {(item.get('vin'))}: {e}")
                item['recalls_data'] = {}
                
            # Calculate completeness flags for clients
            item['data_complete'] = bool(item.get('warranty_data') and item.get('lcdv_data') and item.get('recalls_data'))
            item['pdf_ready'] = bool(item.get('file_path') and not str(item.get('file_path')).startswith('paperless:PROCESSING'))
                
            history.append(item)
            
        return history

def get_stats(days=30):
    with SessionLocal() as db:
        total = db.query(func.count(VehicleHistory.id)).scalar()
        unique_vins = db.query(func.count(func.distinct(VehicleHistory.vin))).scalar()
        
        last_active = db.query(VehicleHistory.timestamp).order_by(VehicleHistory.timestamp.desc()).first()
        last_active = str(last_active[0]) if last_active else "Never"
        
        queue_counts = db.query(Job.status, func.count(Job.job_id)).group_by(Job.status).all()
        queue_dict = {status: count for status, count in queue_counts}
        
        success_count = queue_dict.get("success", 0)
        error_count = queue_dict.get("error", 0)
        total_finished = success_count + error_count
        success_rate = 100
        if total_finished > 0:
            success_rate = round((success_count / total_finished) * 100)
        
        return {
            "total_downloads": total,
            "unique_vins": unique_vins,
            "cache_hits": config_loader.config.get("cache_hits", 0),
            "last_active": last_active,
            "success_rate": success_rate,
            "queue": {
                "queued": queue_dict.get("queued", 0),
                "processing": queue_dict.get("processing", 0),
                "error": queue_dict.get("error", 0),
                "success": queue_dict.get("success", 0)
            }
        }

def delete_old_history(days=30):
    cutoff = datetime.utcnow() - timedelta(days=days)
    with SessionLocal() as db:
        count = db.query(VehicleHistory).filter(VehicleHistory.timestamp < cutoff).delete()
        db.query(Vehicle).filter(Vehicle.last_updated < cutoff).delete()
        db.query(MaintenanceService).filter(MaintenanceService.id.in_(
             db.query(MaintenanceService.id).filter(~MaintenanceService.vin.in_(
                 db.query(Vehicle.vin)
             ))
        )).delete(synchronize_session=False) # Cleanup orphan maintenance records
        db.commit()
        return count

def _parse_interval(interval_str: str) -> dict:
    """
    Parses a maintenance interval string into structured fields.
    Handles formats:
      'Alle 30000 km / 2 Jahr(e)'                         → km_and_time, km=30000, years=2
      'Alle 30000 km'                                      → km_only, km=30000
      'Alle 2 Jahr(e)'                                     → time_only, years=2
      '90000 km Dann alle 30000 km'                        → progressive, km=90000, repeat_km=30000
      '120000 km / 4 Jahr(e) Dann alle 30000 km / 2 Jahr(e)' → progressive with repeat
    """
    import re
    if not interval_str:
        return {"km": None, "years": None, "repeat_km": None, "repeat_years": None, "interval_type": "unknown"}

    s = interval_str.strip()

    def _extract_km(text):
        m = re.search(r'(\d[\d\.]*?)\s*km', text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1).replace('.', '').replace(' ', ''))
            except ValueError:
                pass
        return None

    def _extract_years(text):
        m = re.search(r'(\d+)\s*Jahr', text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
        return None

    # Check for 'Dann alle' — progressive pattern
    dann_parts = re.split(r'Dann alle', s, flags=re.IGNORECASE)
    if len(dann_parts) == 2:
        km = _extract_km(dann_parts[0])
        years = _extract_years(dann_parts[0])
        repeat_km = _extract_km(dann_parts[1])
        repeat_years = _extract_years(dann_parts[1])
        return {"km": km, "years": years, "repeat_km": repeat_km, "repeat_years": repeat_years, "interval_type": "progressive"}

    # Simple patterns
    km = _extract_km(s)
    years = _extract_years(s)

    if km and years:
        interval_type = "km_and_time"
    elif km:
        interval_type = "km_only"
    elif years:
        interval_type = "time_only"
    else:
        interval_type = "unknown"

    return {"km": km, "years": years, "repeat_km": None, "repeat_years": None, "interval_type": interval_type}


def save_maintenance_services(vin: str, services: list):
    if not services:
        return
        
    with SessionLocal() as db:
        db.query(MaintenanceService).filter(MaintenanceService.vin == vin).delete()
        
        for srv in services:
            entry = MaintenanceService(
                vin=vin,
                operation_type=srv.get('type', ''),
                description=srv.get('description', ''),
                interval_standard=srv.get('interval_standard', ''),
                interval_severe=srv.get('interval_severe', '')
            )
            db.add(entry)
            
        db.commit()

def get_maintenance_services(vin: str) -> list:
    with SessionLocal() as db:
        rows = db.query(MaintenanceService).filter(MaintenanceService.vin == vin).all()
        services = []
        for row in rows:
            p_std = _parse_interval(row.interval_standard or "")
            p_sev = _parse_interval(row.interval_severe or "") if row.interval_severe else {}
            services.append({
                'type': row.operation_type,
                'description': row.description,
                'interval_standard': row.interval_standard,
                'interval_severe': row.interval_severe,
                'interval_type': p_std['interval_type'],
                'km': p_std['km'],
                'years': p_std['years'],
                'repeat_km': p_std.get('repeat_km'),
                'repeat_years': p_std.get('repeat_years'),
                'severe_km': p_sev.get('km'),
                'severe_years': p_sev.get('years'),
                'severe_repeat_km': p_sev.get('repeat_km'),
                'severe_repeat_years': p_sev.get('repeat_years'),
            })
        return services
