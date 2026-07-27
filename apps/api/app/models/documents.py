import enum
from uuid import UUID, uuid4
from sqlalchemy import String, Integer, Boolean, ForeignKey, Enum, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class FileType(str, enum.Enum):
    pdf = "pdf"
    html = "html"

class SourceDocument(Base, TimestampMixin):
    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    regulation_version_id: Mapped[UUID] = mapped_column(ForeignKey("regulation_versions.id", use_alter=True, name="fk_source_documents_regulation_version_id"), index=True)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType))
    storage_path: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(String)
    ocr_used: Mapped[bool] = mapped_column(Boolean)
    page_count: Mapped[int] = mapped_column(Integer)

class DocumentSection(Base, TimestampMixin):
    __tablename__ = "document_sections"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_document_id: Mapped[UUID] = mapped_column(ForeignKey("source_documents.id"), index=True)
    reference_label: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(String)
    order_index: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_document_sections_raw_text_gin", text("to_tsvector('english', raw_text)"), postgresql_using="gin"),
    )
