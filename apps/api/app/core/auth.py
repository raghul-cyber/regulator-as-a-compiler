from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.users import User, UserRole
from app.core.config import settings

security = HTTPBearer()

import base64

def get_jwks_url():
    pk = settings.CLERK_PUBLISHABLE_KEY
    if not pk:
        return "https://api.clerk.dev/v1/jwks"
    parts = pk.split('_')
    if len(parts) >= 3:
        b64_str = parts[2]
        b64_str += "=" * ((4 - len(b64_str) % 4) % 4)
        try:
            domain = base64.b64decode(b64_str).decode('utf-8')
            if domain.endswith('$'):
                domain = domain[:-1]
            return f"https://{domain}/.well-known/jwks.json"
        except Exception:
            pass
    return "https://api.clerk.dev/v1/jwks"

try:
    jwks_client = PyJWKClient(get_jwks_url())
except Exception:
    jwks_client = None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    token = credentials.credentials
    print(f"Received token (first 10 chars): {token[:10]}... length: {len(token)}", flush=True)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        # Verify the JWT
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
        )
        clerk_user_id = payload.get("sub")
        if not clerk_user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            # Autovivify user for local dev without webhooks
            import uuid
            from app.models.organizations import Organization
            
            org_stmt = select(Organization).limit(1)
            org_res = await db.execute(org_stmt)
            org = org_res.scalar_one_or_none()
            
            if not org:
                org = Organization(id=uuid.uuid4(), name="Default Org", plan="standard")
                db.add(org)
                await db.commit()
                await db.refresh(org)
                
            user = User(
                id=uuid.uuid4(),
                clerk_user_id=clerk_user_id,
                org_id=org.id,
                role=UserRole.admin,
                email="auto@example.com"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
        return user
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Auth error: {str(e)}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_role(*roles: UserRole):
    """
    Dependency factory to check if the current user has one of the allowed roles.
    """
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user.role}' not authorized. Allowed roles: {[r.value for r in roles]}"
            )
        return user
    return role_checker
