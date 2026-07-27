import enum
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, ForeignKey, Enum, Numeric, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.models.base import Base, TimestampMixin
import sqlalchemy.dialects.postgresql as pg

class RequirementType(str, enum.Enum):
    obligation = "obligation"
    prohibition = "prohibition"
    permission = "permission"

class Severity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class ValidationStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    enforceable = "enforceable"

class Requirement(Base, TimestampMixin):
    __tablename__ = "requirements"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    regulation_version_id: Mapped[UUID] = mapped_column(ForeignKey("regulation_versions.id"), index=True)
    section_id: Mapped[UUID] = mapped_column(ForeignKey("document_sections.id"), index=True)
    type: Mapped[RequirementType] = mapped_column(Enum(RequirementType))
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    conditions: Mapped[dict] = mapped_column(pg.JSONB)
    actions: Mapped[dict] = mapped_column(pg.JSONB)
    severity: Mapped[Severity] = mapped_column(Enum(Severity))
    evidence_required: Mapped[dict] = mapped_column(pg.JSONB)
    references: Mapped[dict] = mapped_column(pg.JSONB)
    confidence_score: Mapped[float] = mapped_column(Numeric)
    validation_status: Mapped[ValidationStatus] = mapped_column(Enum(ValidationStatus))
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_requirements_reg_sev_val", "regulation_version_id", "severity", "validation_status"),
        Index("ix_requirements_description_gin", text("to_tsvector('english', description)"), postgresql_using="gin"),
    )

class RequirementEmbedding(Base, TimestampMixin):
    __tablename__ = "requirement_embeddings"

    requirement_id: Mapped[UUID] = mapped_column(ForeignKey("requirements.id"), primary_key=True, index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    model_used: Mapped[str] = mapped_column(String)

    __table_args__ = (
        Index("ix_req_embeddings_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
    )
