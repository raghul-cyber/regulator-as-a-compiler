import enum
from uuid import UUID, uuid4
from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    dead_letter = "dead_letter"

class BackgroundJob(Base, TimestampMixin):
    __tablename__ = "background_jobs"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), index=True, default=JobStatus.pending)
    payload: Mapped[dict] = mapped_column(pg.JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    retries: Mapped[int] = mapped_column(pg.INTEGER, default=0)
