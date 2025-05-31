from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import json
from pathlib import Path
import shutil
import logging
from celery.result import AsyncResult
from .celery_app import celery_app
from .tasks import process_face_swap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FaceFusion API with Celery", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("/app/uploads")
OUTPUT_DIR = Path("/app/outputs")

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    output_url: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None

class ProcessRequest(BaseModel):
    video_id: str
    image_id: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # 接続が切れている場合は無視
                pass

manager = ConnectionManager()

@app.get("/")
async def root():
    return {"message": "FaceFusion API with Celery is running!"}

@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy", "celery": "connected"}

@app.post("/api/upload/video")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.webm')):
        raise HTTPException(status_code=400, detail="Invalid video format")
    
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"file_id": file_id, "filename": file.filename}

@app.post("/api/upload/image")
async def upload_image(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise HTTPException(status_code=400, detail="Invalid image format")
    
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"file_id": file_id, "filename": file.filename}

@app.post("/api/process")
async def start_face_swap_process(request: ProcessRequest):
    """顔交換処理をCeleryタスクで開始"""
    job_id = str(uuid.uuid4())
    
    # Celeryタスクを開始
    task = process_face_swap.delay(job_id, request.video_id, request.image_id)
    
    logger.info(f"Celeryタスク開始: job_id={job_id}, task_id={task.id}")
    
    return {
        "job_id": job_id,
        "task_id": task.id,
        "status": "queued",
        "message": "処理がキューに追加されました"
    }

@app.get("/api/job/{task_id}")
async def get_job_status(task_id: str):
    """Celeryタスクの状態を取得"""
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        if result.state == "PENDING":
            response = JobStatus(
                job_id=task_id,
                status="pending",
                progress=0,
                message="処理待機中..."
            )
        elif result.state == "PROGRESS":
            response = JobStatus(
                job_id=task_id,
                status="processing",
                progress=result.info.get("current", 0),
                message=result.info.get("status", "処理中...")
            )
        elif result.state == "SUCCESS":
            task_result = result.result
            response = JobStatus(
                job_id=task_id,
                status="completed",
                progress=100,
                output_url=task_result.get("output_url"),
                message=task_result.get("message", "処理完了")
            )
        elif result.state == "FAILURE":
            response = JobStatus(
                job_id=task_id,
                status="failed",
                progress=0,
                error=str(result.info.get("error", "Unknown error")),
                message="処理中にエラーが発生しました"
            )
        else:
            response = JobStatus(
                job_id=task_id,
                status=result.state.lower(),
                progress=0,
                message=f"状態: {result.state}"
            )
        
        # WebSocket経由でブロードキャスト
        await manager.broadcast(json.dumps(response.dict()))
        
        return response
        
    except Exception as e:
        logger.error(f"タスク状態取得エラー: {e}")
        raise HTTPException(status_code=500, detail="タスク状態の取得に失敗しました")

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.get("/api/celery/status")
async def celery_status():
    """Celery worker の状態確認"""
    try:
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        active = inspect.active()
        
        return {
            "workers": stats,
            "active_tasks": active,
            "status": "connected" if stats else "disconnected"
        }
    except Exception as e:
        logger.error(f"Celery状態確認エラー: {e}")
        return {"status": "error", "message": str(e)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # エコーメッセージを送信
            await manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)