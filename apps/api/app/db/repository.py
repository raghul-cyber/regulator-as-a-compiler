from typing import TypeVar, Generic, Type, Optional, List, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.models.base import Base
from app.models.users import User

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession, user: User):
        self.model = model
        self.db = db
        self.user = user

    def _apply_tenant_scope(self, stmt: Any) -> Any:
        # Check if the model has an org_id column
        if hasattr(self.model, "org_id"):
            stmt = stmt.where(self.model.org_id == self.user.org_id)
        return stmt

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id)
        stmt = self._apply_tenant_scope(stmt)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        stmt = select(self.model)
        stmt = self._apply_tenant_scope(stmt)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, obj_in: dict) -> ModelType:
        # Automatically inject org_id if the model supports it
        if hasattr(self.model, "org_id") and "org_id" not in obj_in:
            obj_in["org_id"] = self.user.org_id
            
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(self, id: UUID, obj_in: dict) -> Optional[ModelType]:
        stmt = update(self.model).where(self.model.id == id)
        stmt = self._apply_tenant_scope(stmt)
        stmt = stmt.values(**obj_in).returning(self.model)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one_or_none()

    async def delete(self, id: UUID) -> bool:
        stmt = delete(self.model).where(self.model.id == id)
        stmt = self._apply_tenant_scope(stmt)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
