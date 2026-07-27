from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.models.users import UserRole

class UserResponse(BaseModel):
    id: UUID
    org_id: UUID
    clerk_user_id: str
    role: UserRole
    email: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserUpdateRole(BaseModel):
    role: UserRole
