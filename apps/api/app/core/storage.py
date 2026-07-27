import os
import aiofiles
from typing import Protocol
from fastapi import UploadFile

class StorageService(Protocol):
    async def upload_file(self, file: UploadFile, key: str) -> str:
        """
        Uploads a file to storage and returns the storage path/URI.
        """
        ...

class LocalDiskStorageService:
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        
    async def upload_file(self, file: UploadFile, key: str) -> str:
        file_path = os.path.join(self.base_dir, key)
        # Ensure directories exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # read in 1MB chunks
                await out_file.write(content)
                
        return f"local://{file_path}"

# For Phase 3, we'll instantiate the local mock.
# Later this can be injected or swapped with an S3-based service.
storage_service = LocalDiskStorageService()
