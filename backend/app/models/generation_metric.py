"""LLM 生成指标：每次生成调用的延迟/Token/成本估算，供 dashboard 观察单会话成本。"""
from sqlalchemy import Column, String, DateTime, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.database import Base


class GenerationMetric(Base):
    __tablename__ = "generation_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    kind = Column(String(20), default="invoke")  # invoke / stream
    model = Column(String(50), default="")
    destination = Column(String(50), default="")
    prompt_tokens = Column(Integer, default=0)      # 估算
    completion_tokens = Column(Integer, default=0)  # 估算
    first_token_ms = Column(Integer, default=0)     # 首 token 延迟（stream）
    total_ms = Column(Integer, default=0)
    cost = Column(Float, default=0.0)               # 估算（元）

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<GenerationMetric {self.kind} {self.total_ms}ms cost={self.cost:.4f}>"
