from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

from app.db.session import get_db
from app.core.auth import get_current_user
from app.models.users import User
from app.models.reports import Notification, NotificationType

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

class NotificationResponse(BaseModel):
    id: UUID
    org_id: UUID
    type: NotificationType
    payload: dict
    delivered_at: datetime | None
    created_at: datetime

@router.get("", response_model=List[NotificationResponse])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    stmt = select(Notification).where(
        Notification.org_id == user.org_id
    ).order_by(desc(Notification.created_at))
    
    result = await db.execute(stmt)
    return result.scalars().all()
