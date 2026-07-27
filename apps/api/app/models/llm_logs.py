from uuid import UUID, uuid4
from sqlalchemy import String, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column
import sqlalchemy.dialects.postgresql as pg

from app.models.base import Base, TimestampMixin

class LLMCallLog(Base, TimestampMixin):
    __tablename__ = "llm_call_logs"

    id: Mapped[UUID] = mapped_column(pg.UUID(as_uuid=True), primary_key=True, default=uuid4)
    pipeline_stage: Mapped[str] = mapped_column(String, index=True)
    model_used: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric, default=0.0)
