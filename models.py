import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Index, Boolean
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class VehicleHistory(Base):
    __tablename__ = 'vehicle_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(17), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    file_path = Column(Text)
    warranty_data = Column(Text)
    lcdv_data = Column(Text)
    recall_status = Column(Text)
    recall_message = Column(Text)
    status = Column(Text, default='Success')
    recall_data = Column(Text)

class Vehicle(Base):
    __tablename__ = 'vehicles'
    
    vin = Column(String(17), primary_key=True)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    file_path = Column(Text)
    warranty_data = Column(Text)
    lcdv_data = Column(Text)
    recall_status = Column(Text)
    recall_message = Column(Text)
    recall_data = Column(Text)
    status = Column(Text)
    auto_refresh = Column(Boolean, default=True)

class Job(Base):
    __tablename__ = 'jobs'
    
    job_id = Column(String(36), primary_key=True)
    vin = Column(String(17), nullable=False)
    status = Column(Text, default='queued')
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    result = Column(Text)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    recalls_only = Column(Boolean, default=False)
    progress_message = Column(Text, default='')

class MaintenanceService(Base):
    __tablename__ = 'maintenance_services'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    vin = Column(String(17), nullable=False, index=True)
    operation_type = Column(Text)
    description = Column(Text)
    interval_standard = Column(Text)
    interval_severe = Column(Text)
