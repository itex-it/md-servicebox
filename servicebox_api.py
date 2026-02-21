import os
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, Depends, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from servicebox_downloader import ServiceBoxDownloader
import database
from typing import List
import config_loader
from config_loader import config, logger
from job_manager import job_manager
import json
from paperless_client import paperless_client
import requests

app = FastAPI(title="ServiceBox API", version="1.1")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting ServiceBox API...")
    database.init_db()
    job_manager.start_worker()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down ServiceBox API...")
    job_manager.stop_worker()

# Serve Static Files (Dashboard)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/login.html")

@app.get("/dashboard")
async def dashboard():
    return RedirectResponse(url="/static/dashboard.html")

# Auth Schemes

# Auth Schemes
api_key_header = APIKeyHeader(name="X-Auth-Token", auto_error=False)
api_key_query = APIKeyQuery(name="token", auto_error=False)

async def get_api_key(
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query)
):
    """
    Validates API Key from Header ('X-Auth-Token') or Query Param ('token').
    """
    expected_token = config.get("auth_token")
    if not expected_token:
         # If no token configured, allow open access (or log warning)
         return None
         
    if api_key_header == expected_token:
        return api_key_header
    if api_key_query == expected_token:
        return api_key_query
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing Authentication Token"
    )

# Initialize downloader with a specific downloads folder
DOWNLOAD_DIR = os.path.join(os.getcwd(), config.get("output_dir", "downloads"))
downloader = ServiceBoxDownloader(output_dir=DOWNLOAD_DIR)

# Initialize Database
logger.info("Initializing Database...")
database.init_db()

class VinRequest(BaseModel):
    vin: str
    force_refresh: bool = False
    priority: bool = False
    severe_conditions: bool = False

class RetryRequest(BaseModel):
    job_ids: List[str] = []
    all_failed: bool = False

# Global Active Task Counter
ACTIVE_TASKS = 0

@app.post("/api/maintenance-plan", dependencies=[Depends(get_api_key)])
def get_maintenance_plan(request: VinRequest, background_tasks: BackgroundTasks):
    """
    Triggers the download of the maintenance plan for a given VIN.
    Returns JSON with status and file path.
    """
    global ACTIVE_TASKS
    ACTIVE_TASKS += 1
    
    try:
        # 1. Check Cache (if not forced)
        if not request.force_refresh:
            cached_vehicle = database.get_latest_vehicle(request.vin)
            if cached_vehicle and cached_vehicle.get('file_path') and os.path.exists(cached_vehicle['file_path']):
                print(f"Using cached data for VIN: {request.vin}")
                # Construct response similar to downloader result
                filename = os.path.basename(cached_vehicle['file_path'])
                download_url = f"/api/files/{filename}?token={config.get('auth_token')}"
                
                services_raw = database.get_maintenance_services(request.vin)
                services = []
                for srv in services_raw:
                    interval = srv['interval_severe'] if request.severe_conditions and srv['interval_severe'] else srv['interval_standard']
                    services.append({
                        "type": srv['type'],
                        "description": srv['description'],
                        "interval": interval
                    })
                
                return {
                    "success": True,
                    "vin": request.vin,
                    "file_path": cached_vehicle['file_path'],
                    "vehicle_data": {
                        "warranty": cached_vehicle.get('warranty_data'),
                        "lcdv": cached_vehicle.get('lcdv_data'),
                        "recalls": cached_vehicle.get('recalls_data')
                    },
                    "services": services,
                    "download_url": download_url,
                    "cached": True,
                    "status": "cached"
                }

        # 2. Queue Job (Async)
        job_id = job_manager.add_job(request.vin, request.priority)
        
        return {
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "message": "Job added to queue",
            "queue_position": 0 
        }
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
    finally:
        ACTIVE_TASKS -= 1

@app.get("/api/jobs/{job_id}", dependencies=[Depends(get_api_key)])
def get_job_status(job_id: str):
    job = job_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Parse result if exists
    result = None
    if job['result']:
        try: result = json.loads(job['result'])
        except: pass
        
    return {
        "job_id": job['job_id'],
        "vin": job['vin'],
        "status": job['status'],
        "created_at": job['created_at'],
        "result": result,
        "error_message": job['error_message']
    }

@app.post("/api/jobs/retry", dependencies=[Depends(get_api_key)])
def retry_jobs(request: RetryRequest):
    count = job_manager.retry_failed()
    return {"success": True, "retried_count": count}

@app.delete("/api/queue", dependencies=[Depends(get_api_key)])
def clear_queue():
    count = job_manager.clear_queue()
    return {"success": True, "cleared_count": count}

@app.get("/api/vehicle/{vin}", dependencies=[Depends(get_api_key)])
def get_vehicle_metadata(vin: str):
    cached = database.get_latest_vehicle(vin)
    if not cached:
         raise HTTPException(status_code=404, detail="Vehicle not found in cache")
    
    return {
        "vin": vin,
        "last_updated": cached['last_updated'],
        "status": cached['status'],
        "has_cache": True
    }

@app.get("/api/vehicle/{vin}/services", dependencies=[Depends(get_api_key)])
def get_vehicle_services(vin: str, severe_conditions: bool = False):
    services_raw = database.get_maintenance_services(vin)
    if not services_raw:
        raise HTTPException(status_code=404, detail="Maintenance services not found for this VIN")
        
    services = []
    for srv in services_raw:
        interval = srv['interval_severe'] if severe_conditions and srv['interval_severe'] else srv['interval_standard']
        services.append({
            "type": srv['type'],
            "description": srv['description'],
            "interval": interval
        })
        
    return {"vin": vin, "severe_conditions": severe_conditions, "services": services}

@app.get("/api/jobs", dependencies=[Depends(get_api_key)])
def list_jobs(status: str = None, vin: str = None, limit: int = 50):
    """
    Lists jobs with optional filtering.
    """
    jobs = job_manager.get_all_jobs(status, vin, limit)
    return {"jobs": jobs}

@app.delete("/api/jobs/{job_id}", dependencies=[Depends(get_api_key)])
def delete_job(job_id: str):
    """
    Deletes a specific job.
    """
    count = job_manager.delete_job(job_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "message": f"Job {job_id} deleted"}

@app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(get_api_key)])
def retry_single_job(job_id: str):
    """
    Retries a specific job.
    """
    count = job_manager.retry_job(job_id)
    if count == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "message": f"Job {job_id} queued for retry"}
@app.get("/api/history", dependencies=[Depends(get_api_key)])
def get_all_history(search: str = None, limit: int = 50):
    """
    Retrieves history with optional search.
    """
    try:
        history = database.get_history(search_term=search, limit=limit)
        return {"history": history}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/history/{vin}", dependencies=[Depends(get_api_key)])
async def get_vehicle_history(vin: str):
    """
    Retrieves the extraction history for a specific VIN.
    """
    try:
        history = database.get_history(vin=vin)
        return {"vin": vin, "history": history}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/stats", dependencies=[Depends(get_api_key)])
async def get_stats():
    """
    Returns KPIs for the dashboard.
    """
    stats = database.get_stats()
    processing = stats.get("queue", {}).get("processing", 0)
    stats["active_tasks"] = ACTIVE_TASKS + processing
    return stats

@app.get("/api/logs", dependencies=[Depends(get_api_key)])
async def get_logs(lines: int = 100):
    """
    Returns the last N lines of the log file.
    """
    log_file = "servicebox.log"
    if not os.path.exists(log_file):
        return {"logs": ["Log file not found."]}
        
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            # Simple tail implementation
            all_lines = f.readlines()
            return {"logs": all_lines[-lines:]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {str(e)}"]}

@app.post("/api/system/restart", dependencies=[Depends(get_api_key)])
async def system_restart():
    """
    Triggers a server restart by exiting with code 10.
    The host script must handle the loop.
    """
    logger.warning("Restart requested via API.")
    # We use a background task to allow the response to be sent
    asyncio.create_task(shutdown_server(10))
    return {"message": "Restarting server..."}

@app.post("/api/system/shutdown", dependencies=[Depends(get_api_key)])
async def system_shutdown():
    """
    Triggers a server shutdown (Exit code 0).
    """
    logger.warning("Shutdown requested via API.")
    asyncio.create_task(shutdown_server(0))
    return {"message": "Shutting down server..."}

async def shutdown_server(exit_code):
    await asyncio.sleep(1) # Give time for response
    os._exit(exit_code)

@app.get("/api/files/{filename}", dependencies=[Depends(get_api_key)])
async def get_file(filename: str):
    """
    Serves the downloaded file, either locally or proxying from Paperless.
    """
    if filename.startswith("paperless:"):
        doc_id = filename.replace("paperless:", "")
        if not paperless_client.enabled or not paperless_client.token:
             raise HTTPException(status_code=500, detail="Paperless integration is not configured")
             
        try:
            # Proxy request to Paperless
            paperless_dl_url = f"{paperless_client.url}/api/documents/{doc_id}/download/"
            response = requests.get(paperless_dl_url, headers=paperless_client.headers, stream=True)
            response.raise_for_status()
            
            # Forward the stream to the client
            content_disp = response.headers.get('content-disposition', f'attachment; filename="document_{doc_id}.pdf"')
            return StreamingResponse(
                response.iter_content(chunk_size=8192), 
                media_type=response.headers.get('content-type', 'application/pdf'),
                headers={"Content-Disposition": content_disp}
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch document {doc_id} from Paperless: {e}")
            raise HTTPException(status_code=404, detail="File could not be downloaded from Paperless")
            
    # Fallback to local file download
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    else:
        raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    # Ensure download dir exists
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    logger.info("Starting ServiceBox API Server...")
    logger.info("Docs available at http://localhost:8005/docs")
    # Using 0.0.0.0 to allow external access if needed, but keeping localhost for safety default first
    uvicorn.run(app, host="127.0.0.1", port=8005)
