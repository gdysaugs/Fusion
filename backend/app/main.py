from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import uuid
import httpx
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FaceFusion API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("/app/uploads")
OUTPUT_DIR = Path("/app/outputs")
FACEFUSION_PATH = Path("/workspace/facefusion")  # FaceFusionのインストールパス

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    output_url: Optional[str] = None
    error: Optional[str] = None

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
            await connection.send_text(message)

manager = ConnectionManager()
jobs = {}

@app.get("/")
async def root():
    return {"message": "FaceFusion API is running!"}

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

class ProcessRequest(BaseModel):
    video_id: str
    image_id: str

@app.post("/api/process")
async def process_face_swap(request: ProcessRequest):
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = JobStatus(
        job_id=job_id,
        status="pending",
        progress=0
    )
    
    asyncio.create_task(run_face_swap(job_id, request.video_id, request.image_id))
    
    return {"job_id": job_id}

async def run_face_swap(job_id: str, video_id: str, image_id: str):
    try:
        jobs[job_id].status = "processing"
        jobs[job_id].progress = 10
        await manager.broadcast(json.dumps(jobs[job_id].dict()))
        
        # ファイルパスを取得
        video_files = list(UPLOAD_DIR.glob(f"{video_id}_*"))
        image_files = list(UPLOAD_DIR.glob(f"{image_id}_*"))
        
        if not video_files or not image_files:
            raise Exception("アップロードファイルが見つかりません")
        
        source_image = str(image_files[0])
        target_video = str(video_files[0])
        output_filename = f"{job_id}_output.mp4"
        output_path = str(OUTPUT_DIR / output_filename)
        
        logger.info(f"処理開始: source={source_image}, target={target_video}, output={output_path}")
        
        # FaceFusionコマンドを構築
        cmd = [
            "python3",
            str(FACEFUSION_PATH / "facefusion.py"),
            "headless-run",
            "--source", source_image,
            "--target", target_video,
            "--output-path", output_path,
            "--execution-providers", "cuda",
            "--execution-thread-count", "2",  # 4GB VRAMに配慮
            "--face-detector-model", "yolo_face",
            "--face-detector-score", "0.5",
            "--processors", "face_swapper",
            "--log-level", "debug"
        ]
        
        # プロセスを非同期で実行
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(FACEFUSION_PATH)
        )
        
        # 進捗を監視
        jobs[job_id].progress = 20
        await manager.broadcast(json.dumps(jobs[job_id].dict()))
        
        # 出力を非同期で読み取り
        async def read_output():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_text = line.decode().strip()
                logger.info(f"FaceFusion stdout: {line_text}")
                
                # 進捗を更新（簡易的な実装）
                if "Processing" in line_text or "processing" in line_text.lower():
                    current_progress = jobs[job_id].progress
                    if current_progress < 90:
                        jobs[job_id].progress = min(current_progress + 10, 90)
                        await manager.broadcast(json.dumps(jobs[job_id].dict()))
        
        # エラー出力も読み取り
        async def read_error():
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line_text = line.decode().strip()
                logger.info(f"FaceFusion stderr: {line_text}")
        
        # 出力読み取りタスクを開始
        output_task = asyncio.create_task(read_output())
        error_task = asyncio.create_task(read_error())
        
        # プロセスの終了を待つ
        return_code = await process.wait()
        await output_task
        await error_task
        
        if return_code == 0 and os.path.exists(output_path):
            # 成功
            jobs[job_id].status = "completed"
            jobs[job_id].progress = 100
            jobs[job_id].output_url = f"/api/download/{output_filename}"
            logger.info(f"処理完了: {output_path}")
        else:
            # エラー
            stderr = await process.stderr.read()
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise Exception(f"FaceFusion処理エラー: {error_msg}")
        
        await manager.broadcast(json.dumps(jobs[job_id].dict()))
        
    except Exception as e:
        logger.error(f"顔交換処理エラー: {e}")
        jobs[job_id].status = "failed"
        jobs[job_id].error = str(e)
        await manager.broadcast(json.dumps(jobs[job_id].dict()))

@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Echo: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)