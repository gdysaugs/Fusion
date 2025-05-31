from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path

class Settings(BaseSettings):
    # Application Settings
    app_name: str = "FaceFusion API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # CORS Settings
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    cors_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    # File Upload Settings
    max_upload_size_mb: int = 100
    allowed_video_extensions: List[str] = [".mp4", ".avi", ".mov", ".webm"]
    allowed_image_extensions: List[str] = [".jpg", ".jpeg", ".png"]
    
    # FaceFusion Service
    facefusion_url: str = "http://facefusion:7860"
    facefusion_timeout: int = 300
    
    # Storage Settings
    upload_dir: Path = Path("/app/uploads")
    output_dir: Path = Path("/app/outputs")
    cleanup_interval_hours: int = 24
    
    # Security
    secret_key: str = "your-secret-key-here"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Redis Configuration
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Monitoring
    log_level: str = "INFO"
    sentry_dsn: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024
    
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

# Create settings instance
settings = Settings()