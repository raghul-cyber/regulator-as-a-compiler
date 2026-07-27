import time
import redis.asyncio as redis
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.db.session import get_db
from app.models.organizations import Organization
from app.core.api_keys import ApiKey, get_api_key

redis_client = redis.from_url(settings.REDIS_URL)

PLAN_LIMITS = {
    "trial": 10,
    "standard": 100,
    "enterprise": 1000
}

async def rate_limit_by_plan(
    api_key_obj: ApiKey = Depends(get_api_key()),
    db: AsyncSession = Depends(get_db)
):
    # Get organization to check plan
    stmt = select(Organization).where(Organization.id == api_key_obj.org_id)
    org = (await db.execute(stmt)).scalar_one_or_none()
    
    if not org:
        raise HTTPException(status_code=400, detail="Organization not found")
        
    limit = PLAN_LIMITS.get(org.plan.value, 10)
    
    # Simple sliding window rate limit using Redis
    now = int(time.time())
    window_key = f"rate_limit:{org.id}:{now // 60}"
    
    # Increment the counter
    current = await redis_client.incr(window_key)
    
    # Set expiry on first request in window
    if current == 1:
        await redis_client.expire(window_key, 60)
        
    if current > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Plan '{org.plan.value}' allows {limit} requests per minute."
        )
        
    return api_key_obj
