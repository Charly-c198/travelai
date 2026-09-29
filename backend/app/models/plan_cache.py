"""相似行程缓存模型：复用已生成的高质量行程，减少重复 LLM 生成调用。"""
from sqlalchemy import Column, String, DateTime, Integer, Text, JSON
from datetime import datetime

from app.database import Base


class PlanCache(Base):
    """已生成行程的缓存。按 cache_key 去重（保留最新）。"""
    __tablename__ = "plan_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(64), unique=True, nullable=False, index=True)
    destination = Column(String(64), nullable=False, index=True)
    days = Column(Integer, default=0)
    travel_style = Column(String(32), default="")
    budget = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    itinerary = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<PlanCache {self.destination} {self.days}天/{self.travel_style}>"