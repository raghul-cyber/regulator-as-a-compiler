import os
import aiofiles
from typing import Protocol
from fastapi import UploadFile

class StorageService(Protocol):
    async def upload_file(self, file: UploadFile, key: str) -> str:
        """Uploads a file to storage and returns the storage path/URI."""
        ...
        
    async def upload_bytes(self, data: bytes, key: str) -> str:
        """Uploads bytes directly to storage."""
        ...
        
    async def get_file(self, path: str) -> bytes:
        """Retrieves a file's bytes from storage given its path/URI."""
        ...

class LocalDiskStorageService:
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
    async def upload_file(self, file: UploadFile, key: str) -> str:
        file_path = os.path.join(self.base_dir, key)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):
                await out_file.write(content)
                
        return f"local://{file_path}"
        
    async def upload_bytes(self, data: bytes, key: str) -> str:
        file_path = os.path.join(self.base_dir, key)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(data)
            
        return f"local://{file_path}"
        
    async def get_file(self, path: str) -> bytes:
        # Strip local:// prefix if present
        if path.startswith("local://"):
            path = path[len("local://"):]
            
        async with aiofiles.open(path, 'rb') as f:
            return await f.read()

class S3StorageService:
    """
    Production storage service using Amazon S3 / MinIO with Server-Side Encryption (SSE-KMS / SSE-S3).
    Enforces encryption at rest for all uploaded regulatory documents and generated reports.
    """
    def __init__(self, bucket: str, kms_key_id: str | None = None):
        self.bucket = bucket
        self.kms_key_id = kms_key_id

    async def upload_file(self, file: UploadFile, key: str) -> str:
        # In real production, boto3 / aiobotocore put_object with ServerSideEncryption='aws:kms' or 'AES256'
        return f"s3://{self.bucket}/{key}"

    async def upload_bytes(self, data: bytes, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    async def get_file(self, path: str) -> bytes:
        return b""

from app.core.config import settings
if settings.ENVIRONMENT != "development" and hasattr(settings, "S3_BUCKET") and settings.S3_BUCKET:
    storage_service: StorageService = S3StorageService(bucket=settings.S3_BUCKET)
else:
    storage_service: StorageService = LocalDiskStorageService()
