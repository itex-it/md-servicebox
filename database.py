import json
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, select, update, delete, func, desc, or_
from sqlalchemy.orm import sessionmaker

from models import Base, VehicleHistory, Vehicle, Job, MaintenanceService

CONFIG_FILE = "config.json"

def get_db_url():
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Default to SQLite if missing
            return config.get('db_connection', 'sqlite:///servicebox_history.db')
    except Exception:
        return 'sqlite:///servicebox_history.db'

# Create engine, use connect_args for SQLite to avoid thread issues just in case
url = get_db_url()
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}

engine = create_engine(url, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    print(f"[DB] Initializing database at {url}")
    Base.metadata.create_all(bind=engine)

def save_extraction(vin, file_path, vehicle_data, status='Success'):
    with SessionLocal() as db:
        warranty_obj = vehicle_data.get('warranty') or vehicle_data.get('warranty_details') or {}
        warranty = json.dumps(warranty_obj)
        lcdv = json.dumps(vehicle_data.get('lcdv', {}))
        recalls = vehicle_data.get('recalls', {})
        recall_status = recalls.get('status', 'Unknown')
        recall_message = recalls.get('message', '')
        recall_data = json.dumps(recalls)
        
        # Insert History
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
        
        # Upsert Vehicle (merge)
        vehicle = db.query(Vehicle).filter(Vehicle.vin == vin).first()
        if vehicle:
            vehicle.file_path = file_path
            vehicle.warranty_data = warranty
            vehicle.lcdv_data = lcdv
            vehicle.recall_status = recall_status
            vehicle.recall_message = recall_message
            vehicle.status = status
            vehicle.recall_data = recall_data
        else:
            vehicle = Vehicle(
                vin=vin,
                file_path=file_path,
                warranty_data=warranty,
                lcdv_data=lcdv,
                recall_status=recall_status,
                recall_message=recall_message,
                status=status,
                recall_data=recall_data
            )
            db.add(vehicle)
            
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

def create_job(job_id, vin, priority=0):
    with SessionLocal() as db:
        job = Job(job_id=job_id, vin=vin, status='queued', priority=priority)
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
        stuck_jobs = db.query(Job).filter(Job.status == 'processing').all()
        for job in stuck_jobs:
            job.status = 'error'
            job.error_message = 'Job was interrupted by server shutdown/restart.'
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
        
        return {
            "total_downloads": total,
            "unique_vins": unique_vins,
            "last_active": last_active,
            "success_rate": 100,
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
            services.append({
                'type': row.operation_type,
                'description': row.description,
                'interval_standard': row.interval_standard,
                'interval_severe': row.interval_severe
            })
        return services
