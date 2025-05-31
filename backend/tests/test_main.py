import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import tempfile
import shutil
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main_improved import app, settings

# Override settings for testing
settings.upload_dir = Path(tempfile.mkdtemp())
settings.output_dir = Path(tempfile.mkdtemp())

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    # Cleanup temporary directories after tests
    shutil.rmtree(settings.upload_dir, ignore_errors=True)
    shutil.rmtree(settings.output_dir, ignore_errors=True)

def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "version" in response.json()

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_upload_video_invalid_format():
    """Test video upload with invalid format"""
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
        tmp.write(b"test content")
        tmp.seek(0)
        response = client.post(
            "/api/upload/video",
            files={"file": ("test.txt", tmp, "text/plain")}
        )
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]

def test_upload_video_success():
    """Test successful video upload"""
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        tmp.write(b"fake video content")
        tmp.seek(0)
        response = client.post(
            "/api/upload/video",
            files={"file": ("test.mp4", tmp, "video/mp4")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert "filename" in data

def test_upload_image_invalid_format():
    """Test image upload with invalid format"""
    with tempfile.NamedTemporaryFile(suffix=".bmp") as tmp:
        tmp.write(b"test content")
        tmp.seek(0)
        response = client.post(
            "/api/upload/image",
            files={"file": ("test.bmp", tmp, "image/bmp")}
        )
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]

def test_upload_image_success():
    """Test successful image upload"""
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        tmp.write(b"fake image content")
        tmp.seek(0)
        response = client.post(
            "/api/upload/image",
            files={"file": ("test.jpg", tmp, "image/jpeg")}
        )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert "filename" in data

def test_process_missing_files():
    """Test process with missing files"""
    response = client.post(
        "/api/process",
        json={"video_id": "nonexistent", "image_id": "nonexistent"}
    )
    assert response.status_code == 404

def test_get_job_not_found():
    """Test getting non-existent job"""
    response = client.get("/api/job/nonexistent")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]

def test_download_file_not_found():
    """Test downloading non-existent file"""
    response = client.get("/api/download/nonexistent.mp4")
    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]

def test_list_jobs():
    """Test listing jobs"""
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert "jobs" in response.json()
    assert isinstance(response.json()["jobs"], list)

@pytest.mark.asyncio
async def test_websocket():
    """Test WebSocket connection"""
    with client.websocket_connect("/ws/test-client") as websocket:
        websocket.send_text("Hello")
        data = websocket.receive_text()
        assert data == "Echo: Hello"

def test_sanitize_filename():
    """Test filename sanitization"""
    from app.main_improved import sanitize_filename
    
    assert sanitize_filename("normal_file.mp4") == "normal_file.mp4"
    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("file with spaces.mp4") == "file with spaces.mp4"
    assert sanitize_filename("file@#$%^&*.mp4") == "file.mp4"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])