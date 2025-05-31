from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
import uuid
import httpx
import asyncio
import json
import logging
from pathlib import Path
import shutil
from datetime import datetime, timedelta
import aiofiles
from contextlib import asynccontextmanager

from .config import settings

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Job storage with TTL
class JobStore:
    def __init__(self, ttl_hours: int = 24):
        self.jobs: Dict[str, tuple[JobStatus, datetime]] = {}
        self.ttl = timedelta(hours=ttl_hours)
    
    def add_job(self, job_id: str, job: 'JobStatus'):
        self.jobs[job_id] = (job, datetime.now())
        self._cleanup_old_jobs()
    
    def get_job(self, job_id: str) -> Optional['JobStatus']:
        if job_id in self.jobs:
            job, timestamp = self.jobs[job_id]
            if datetime.now() - timestamp < self.ttl:
                return job
            else:
                del self.jobs[job_id]
        return None
    
    def update_job(self, job_id: str, job: 'JobStatus'):
        if job_id in self.jobs:
            self.jobs[job_id] = (job, self.jobs[job_id][1])
    
    def _cleanup_old_jobs(self):
        current_time = datetime.now()
        expired_jobs = [
            job_id for job_id, (_, timestamp) in self.jobs.items()
            if current_time - timestamp >= self.ttl
        ]
        for job_id in expired_jobs:
            del self.jobs[job_id]

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting FaceFusion API...")
    settings.upload_dir.mkdir(exist_ok=True)
    settings.output_dir.mkdir(exist_ok=True)
    
    # Initialize HTTP client
    app.state.http_client = httpx.AsyncClient(timeout=settings.facefusion_timeout)
    
    yield
    
    # Shutdown
    logger.info("Shutting down FaceFusion API...")
    await app.state.http_client.aclose()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan
)

# CORS middleware with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: int
    output_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()

class ProcessRequest(BaseModel):
    video_id: str
    image_id: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client {client_id} connected")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket client {client_id} disconnected")
    
    async def send_to_client(self, message: str, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(message)
            except Exception as e:
                logger.error(f"Error sending message to client {client_id}: {e}")
                self.disconnect(client_id)
    
    async def broadcast(self, message: str):
        disconnected_clients = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        for client_id in disconnected_clients:
            self.disconnect(client_id)

# Initialize managers
manager = ConnectionManager()
job_store = JobStore(ttl_hours=settings.cleanup_interval_hours)

# Utility functions
def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    import re
    # Remove any path separators and special characters
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\s.-]', '', filename)
    return filename[:255]  # Limit filename length

async def save_upload_file(upload_file: UploadFile, allowed_extensions: List[str]) -> tuple[str, Path]:
    """Save uploaded file with validation"""
    # Validate file extension
    file_ext = Path(upload_file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Allowed formats: {', '.join(allowed_extensions)}"
        )
    
    # Check file size
    if upload_file.size and upload_file.size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB"
        )
    
    # Generate safe filename
    file_id = str(uuid.uuid4())
    safe_filename = sanitize_filename(upload_file.filename)
    file_path = settings.upload_dir / f"{file_id}_{safe_filename}"
    
    # Save file asynchronously
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            while chunk := await upload_file.read(8192):  # Read in chunks
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise HTTPException(status_code=500, detail="Error saving file")
    
    return file_id, file_path

# API Endpoints
@app.get("/")
async def root():
    return {
        "message": "FaceFusion API is running!",
        "version": settings.app_version,
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/upload/video")
async def upload_video(file: UploadFile = File(...)):
    """Upload video file"""
    try:
        file_id, file_path = await save_upload_file(file, settings.allowed_video_extensions)
        logger.info(f"Video uploaded: {file_id}")
        return {
            "file_id": file_id,
            "filename": file.filename,
            "size": file.size
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(status_code=500, detail="Error uploading video")

@app.post("/api/upload/image")
async def upload_image(file: UploadFile = File(...)):
    """Upload image file"""
    try:
        file_id, file_path = await save_upload_file(file, settings.allowed_image_extensions)
        logger.info(f"Image uploaded: {file_id}")
        return {
            "file_id": file_id,
            "filename": file.filename,
            "size": file.size
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail="Error uploading image")

@app.post("/api/process")
async def process_face_swap(request: ProcessRequest):
    """Start face swap processing"""
    job_id = str(uuid.uuid4())
    
    # Validate input files exist
    video_files = list(settings.upload_dir.glob(f"{request.video_id}_*"))
    image_files = list(settings.upload_dir.glob(f"{request.image_id}_*"))
    
    if not video_files:
        raise HTTPException(status_code=404, detail="Video file not found")
    if not image_files:
        raise HTTPException(status_code=404, detail="Image file not found")
    
    # Create job
    job = JobStatus(
        job_id=job_id,
        status="pending",
        progress=0
    )
    job_store.add_job(job_id, job)
    
    # Start processing in background
    asyncio.create_task(run_face_swap(job_id, video_files[0], image_files[0]))
    
    logger.info(f"Job created: {job_id}")
    return {"job_id": job_id}

async def run_face_swap(job_id: str, video_path: Path, image_path: Path):
    """Run face swap processing with FaceFusion"""
    http_client = app.state.http_client
    
    try:
        # Update job status
        job = job_store.get_job(job_id)
        if not job:
            return
        
        job.status = "processing"
        job.progress = 10
        job.updated_at = datetime.now()
        job_store.update_job(job_id, job)
        await manager.broadcast(json.dumps(job.dict()))
        
        # Prepare request to FaceFusion
        files = {
            'source': open(image_path, 'rb'),
            'target': open(video_path, 'rb')
        }
        
        data = {
            'face_selector_mode': 'many',
            'face_analyser_order': 'left-right',
            'face_analyser_age': 'all',
            'face_analyser_gender': 'all',
            'face_detector_model': 'retinaface',
            'face_recognizer_model': 'arcface_inswapper',
            'face_mask_type': 'box',
            'face_enhancer_model': 'gfpgan_1.4',
            'frame_enhancer_model': 'real_esrgan_x4plus',
            'execution_providers': ['cpu'],
            'execution_thread_count': 4,
            'execution_queue_count': 1
        }
        
        # Send request to FaceFusion
        logger.info(f"Sending request to FaceFusion for job {job_id}")
        
        try:
            response = await http_client.post(
                f"{settings.facefusion_url}/api/process",
                files=files,
                data=data
            )
            response.raise_for_status()
            
            # Process response
            result = response.json()
            
            # Update progress periodically
            for progress in [30, 50, 70, 90]:
                job.progress = progress
                job.updated_at = datetime.now()
                job_store.update_job(job_id, job)
                await manager.broadcast(json.dumps(job.dict()))
                await asyncio.sleep(2)
            
            # Save output
            output_filename = f"{job_id}_output.mp4"
            output_path = settings.output_dir / output_filename
            
            # Download processed video from FaceFusion
            if 'output_url' in result:
                output_response = await http_client.get(result['output_url'])
                output_response.raise_for_status()
                
                async with aiofiles.open(output_path, 'wb') as f:
                    await f.write(output_response.content)
            
            # Update job as completed
            job.status = "completed"
            job.progress = 100
            job.output_url = f"/api/download/{output_filename}"
            job.updated_at = datetime.now()
            job_store.update_job(job_id, job)
            
            logger.info(f"Job completed: {job_id}")
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during FaceFusion processing: {e}")
            raise Exception(f"FaceFusion API error: {str(e)}")
        
        finally:
            # Close file handles
            for file_handle in files.values():
                file_handle.close()
        
        await manager.broadcast(json.dumps(job.dict()))
        
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        job = job_store.get_job(job_id)
        if job:
            job.status = "failed"
            job.error = str(e)
            job.updated_at = datetime.now()
            job_store.update_job(job_id, job)
            await manager.broadcast(json.dumps(job.dict()))

@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/jobs")
async def list_jobs():
    """List all active jobs"""
    jobs = []
    for job_id in list(job_store.jobs.keys()):
        job = job_store.get_job(job_id)
        if job:
            jobs.append(job)
    return {"jobs": jobs}

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Download processed file"""
    # Sanitize filename to prevent path traversal
    safe_filename = sanitize_filename(filename)
    file_path = settings.output_dir / safe_filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if file is within output directory
    if not str(file_path).startswith(str(settings.output_dir)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        file_path,
        media_type='video/mp4',
        filename=safe_filename
    )

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now, can be extended for bidirectional communication
            await manager.send_to_client(f"Echo: {data}", client_id)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers
    )