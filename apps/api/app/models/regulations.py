from datetime import date
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class Regulation(Base, TimestampMixin):
    __tablename__ = "regulations"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String)
    jurisdiction: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    current_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("regulation_versions.id", use_alter=True, name="fk_regulations_current_version_id"), nullable=True, index=True)

class RegulationVersion(Base, TimestampMixin):
    __tablename__ = "regulation_versions"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    regulation_id: Mapped[UUID] = mapped_column(ForeignKey("regulations.id"), index=True)
    version_label: Mapped[str] = mapped_column(String)
    published_date: Mapped[date] = mapped_column(Date)
    ingested_at: Mapped[date] = mapped_column(pg.TIMESTAMP(timezone=True))
    source_document_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True, index=True)
    diff_summary: Mapped[dict | None] = mapped_column(pg.JSONB, nullable=True)
