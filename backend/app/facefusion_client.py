import httpx
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)

class FaceFusionClient:
    """Client for interacting with FaceFusion API"""
    
    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = base_url or settings.facefusion_url
        self.timeout = timeout or settings.facefusion_timeout
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def check_health(self) -> bool:
        """Check if FaceFusion service is healthy"""
        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"FaceFusion health check failed: {e}")
            return False
    
    async def process_face_swap(
        self,
        source_image_path: Path,
        target_video_path: Path,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process face swap with FaceFusion
        
        Args:
            source_image_path: Path to source face image
            target_video_path: Path to target video
            options: Processing options
        
        Returns:
            Processing result with output URL
        """
        default_options = {
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
        
        if options:
            default_options.update(options)
        
        try:
            with open(source_image_path, 'rb') as source_file, \
                 open(target_video_path, 'rb') as target_file:
                
                files = {
                    'source': ('source.jpg', source_file, 'image/jpeg'),
                    'target': ('target.mp4', target_file, 'video/mp4')
                }
                
                response = await self.client.post(
                    "/api/process",
                    files=files,
                    data=default_options
                )
                response.raise_for_status()
                
                return response.json()
        
        except httpx.HTTPStatusError as e:
            logger.error(f"FaceFusion API error: {e.response.status_code} - {e.response.text}")
            raise Exception(f"FaceFusion processing failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error during face swap processing: {e}")
            raise
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get processing job status"""
        try:
            response = await self.client.get(f"/api/job/{job_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            raise
    
    async def download_output(self, output_url: str, save_path: Path) -> None:
        """Download processed output file"""
        try:
            response = await self.client.get(output_url)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded output to: {save_path}")
        except Exception as e:
            logger.error(f"Error downloading output: {e}")
            raise

# Example usage
async def example_usage():
    async with FaceFusionClient() as client:
        # Check health
        is_healthy = await client.check_health()
        print(f"FaceFusion service healthy: {is_healthy}")
        
        # Process face swap
        result = await client.process_face_swap(
            source_image_path=Path("/path/to/source.jpg"),
            target_video_path=Path("/path/to/target.mp4")
        )
        print(f"Processing result: {result}")
        
        # Download output
        if 'output_url' in result:
            await client.download_output(
                output_url=result['output_url'],
                save_path=Path("/path/to/output.mp4")
            )

if __name__ == "__main__":
    asyncio.run(example_usage())