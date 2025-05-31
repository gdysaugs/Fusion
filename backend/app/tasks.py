import os
import asyncio
import subprocess
import logging
from pathlib import Path
from celery import current_task
from celery.exceptions import Ignore
from .celery_app import celery_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("/app/uploads")
OUTPUT_DIR = Path("/app/outputs")
FACEFUSION_PATH = Path("/workspace/facefusion")

@celery_app.task(bind=True, name="app.tasks.process_face_swap")
def process_face_swap(self, job_id: str, video_id: str, image_id: str):
    """
    Face swap processing task using Celery
    """
    try:
        # 進捗状況を更新
        self.update_state(
            state="PROGRESS",
            meta={"current": 10, "total": 100, "status": "ファイル検索中..."}
        )
        
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
        
        # 進捗状況を更新
        self.update_state(
            state="PROGRESS",
            meta={"current": 20, "total": 100, "status": "FaceFusion処理を開始中..."}
        )
        
        # FaceFusionコマンドを構築
        cmd = [
            "python3",
            str(FACEFUSION_PATH / "facefusion.py"),
            "headless-run",
            "--source", source_image,
            "--target", target_video,
            "--output-path", output_path,
            "--execution-providers", "cuda",
            "--execution-thread-count", "2",
            "--face-detector-model", "yolo_face",
            "--face-detector-score", "0.5",
            "--processors", "face_swapper",
            "--log-level", "info"
        ]
        
        # 進捗状況を更新
        self.update_state(
            state="PROGRESS",
            meta={"current": 30, "total": 100, "status": "顔交換処理実行中..."}
        )
        
        # プロセスを実行（同期処理でCeleryタスク内）
        process = subprocess.run(
            cmd,
            cwd=str(FACEFUSION_PATH),
            capture_output=True,
            text=True,
            timeout=1800  # 30分のタイムアウト
        )
        
        # 進捗状況を更新
        self.update_state(
            state="PROGRESS",
            meta={"current": 80, "total": 100, "status": "処理結果を確認中..."}
        )
        
        # 結果を確認
        if process.returncode == 0 and os.path.exists(output_path):
            # 成功
            logger.info(f"処理完了: {output_path}")
            self.update_state(
                state="PROGRESS",
                meta={"current": 100, "total": 100, "status": "処理完了"}
            )
            
            return {
                "status": "completed",
                "output_url": f"/api/download/{output_filename}",
                "message": "顔交換処理が正常に完了しました"
            }
        else:
            # エラー
            error_msg = process.stderr if process.stderr else "Unknown error"
            logger.error(f"FaceFusion処理エラー: {error_msg}")
            raise Exception(f"FaceFusion処理エラー: {error_msg}")
            
    except Exception as e:
        logger.error(f"顔交換処理エラー: {e}")
        self.update_state(
            state="FAILURE",
            meta={"error": str(e)}
        )
        raise Ignore()