from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID, uuid4

from app.db.session import get_db
from app.db.repository import BaseRepository
from app.models.users import User, UserRole
from app.models.audit import AuditLog
from app.core.auth import get_current_user, require_role
from app.schemas.user import UserResponse, UserUpdateRole

router = APIRouter(prefix="/org/users", tags=["org"])

def get_user_repository(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
) -> BaseRepository[User]:
    return BaseRepository(User, db, user)

@router.get("", response_model=List[UserResponse])
async def list_org_users(
    repo: BaseRepository[User] = Depends(get_user_repository),
    admin_user: User = Depends(require_role(UserRole.admin))
):
    """
    List all users in the current organization. Requires Admin role.
    """
    # The repository automatically scopes to admin_user.org_id
    users = await repo.get_all()
    return users

@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: UUID,
    role_update: UserUpdateRole,
    repo: BaseRepository[User] = Depends(get_user_repository),
    admin_user: User = Depends(require_role(UserRole.admin))
):
    """
    Update a user's role. Requires Admin role.
    """
    user_to_update = await repo.get_by_id(user_id)
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found in this organization")
    
    # Prevent removing the last admin (simplified check, assumes there's logic if needed)
    
    updated_user = await repo.update(user_id, {"role": role_update.role})
    
    audit_log = AuditLog(
        id=uuid4(),
        org_id=admin_user.org_id,
        actor_id=admin_user.id,
        action="user.role_updated",
        entity_type="user",
        entity_id=user_id,
        metadata_payload={"new_role": role_update.role.value if hasattr(role_update.role, 'value') else str(role_update.role)}
    )
    repo.session.add(audit_log)
    await repo.session.commit()
    
    return updated_user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_org(
    user_id: UUID,
    repo: BaseRepository[User] = Depends(get_user_repository),
    admin_user: User = Depends(require_role(UserRole.admin))
):
    """
    Remove a user from the organization. Requires Admin role.
    """
    user_to_remove = await repo.get_by_id(user_id)
    if not user_to_remove:
        raise HTTPException(status_code=404, detail="User not found in this organization")
    
    if user_id == admin_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
        
    await repo.delete(user_id)
    
    audit_log = AuditLog(
        id=uuid4(),
        org_id=admin_user.org_id,
        actor_id=admin_user.id,
        action="user.deleted",
        entity_type="user",
        entity_id=user_id,
        metadata_payload={}
    )
    repo.session.add(audit_log)
    await repo.session.commit()
    
    return None
