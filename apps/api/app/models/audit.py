from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, ImmutableTimestampMixin
import sqlalchemy.dialects.postgresql as pg

class AuditLog(Base, ImmutableTimestampMixin):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True))
    metadata_payload: Mapped[dict] = mapped_column(pg.JSONB)  # Using metadata_payload since metadata is reserved in SQLAlchemy
