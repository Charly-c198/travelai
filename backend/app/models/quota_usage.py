"""额度/订阅用量模型：每日高质量生成计数 + 用户权益（free/pro）。"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.database import Base


class QuotaUsage(Base):
    __tablename__ = "quota_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(String(10), nullable=False, default=lambda: datetime.utcnow().strftime("%Y-%m-%d"))
    used_count = Column(Integer, default=0)
    plan = Column(String(10), default="free")  # free / pro
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("uq_date_user", "user_id", "date", unique=True),)

    def __repr__(self):
        return f"<QuotaUsage {self.user_id} {self.date} used={self.used_count} plan={self.plan}>"