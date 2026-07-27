import enum
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class DiffStatus(str, enum.Enum):
    added = "added"
    removed = "removed"
    modified = "modified"
    unchanged = "unchanged"

class RequirementDiff(Base, TimestampMixin):
    __tablename__ = "requirement_diffs"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    regulation_version_id: Mapped[UUID] = mapped_column(ForeignKey("regulation_versions.id"), index=True)
    old_requirement_id: Mapped[UUID | None] = mapped_column(ForeignKey("requirements.id"), index=True, nullable=True)
    new_requirement_id: Mapped[UUID | None] = mapped_column(ForeignKey("requirements.id"), index=True, nullable=True)
    status: Mapped[DiffStatus] = mapped_column(Enum(DiffStatus))
