import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class ReportType(str, enum.Enum):
    executive_summary = "executive_summary"
    technical = "technical"
    audit_evidence = "audit_evidence"
    gap_analysis = "gap_analysis"
    checklist = "checklist"

class NotificationType(str, enum.Enum):
    impact_alert = "impact_alert"
    version_change = "version_change"
    report_ready = "report_ready"

class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    regulation_id: Mapped[UUID] = mapped_column(ForeignKey("regulations.id"), index=True)
    report_type: Mapped[ReportType] = mapped_column(Enum(ReportType))
    storage_path: Mapped[str] = mapped_column(String)
    generated_at: Mapped[datetime] = mapped_column(pg.TIMESTAMP(timezone=True))

class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    payload: Mapped[dict] = mapped_column(pg.JSONB)
    delivered_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True), nullable=True)
