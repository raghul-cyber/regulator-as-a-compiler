import enum
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg
from app.models.requirements import Severity

class ImpactStatus(str, enum.Enum):
    unresolved = "unresolved"
    acknowledged = "acknowledged"
    resolved = "resolved"

class ImpactRecord(Base, TimestampMixin):
    __tablename__ = "impact_records"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    system_mapping_id: Mapped[UUID] = mapped_column(ForeignKey("system_mappings.id"), index=True)
    requirement_diff_id: Mapped[UUID] = mapped_column(ForeignKey("requirement_diffs.id"), index=True)
    
    # Inherited from the requirement by default
    severity: Mapped[Severity] = mapped_column(Enum(Severity))
    # If the org wants to override the inherited severity for this system
    overridden_severity: Mapped[Severity | None] = mapped_column(Enum(Severity), nullable=True)
    
    status: Mapped[ImpactStatus] = mapped_column(Enum(ImpactStatus), default=ImpactStatus.unresolved)
