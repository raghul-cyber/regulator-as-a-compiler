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

# For Phase 3, we'll instantiate the local mock.
# Later this can be injected or swapped with an S3-based service.
storage_service = LocalDiskStorageService()
