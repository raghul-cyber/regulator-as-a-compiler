import hashlib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.api_keys import ApiKey

api_key_security = HTTPBearer()

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()

def get_api_key(required_scopes: list[str] = None):
    async def dependency(
        credentials: HTTPAuthorizationCredentials = Depends(api_key_security),
        db: AsyncSession = Depends(get_db)
    ) -> ApiKey:
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API Key"
            )
        
        token = credentials.credentials
        key_hash = hash_api_key(token)
        
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = await db.execute(stmt)
        api_key_obj = result.scalar_one_or_none()
        
        if not api_key_obj:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key"
            )
            
        if api_key_obj.revoked_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key has been revoked"
            )
            
        if required_scopes:
            has_scope = any(scope in api_key_obj.scopes for scope in required_scopes)
            if not has_scope:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API Key missing required scope. Allowed: {required_scopes}"
                )
                    
        return api_key_obj
        
    return dependency
