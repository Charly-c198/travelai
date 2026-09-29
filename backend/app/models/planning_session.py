"""规划状态持久化模型：按 user+会话存最近一份 plan 对象（多轮修改的事实唯一真源）。"""
from sqlalchemy import Column, String, JSON, DateTime, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class PlanningSession(Base):
    """最近一份规划状态。

    - plan_spec_json: PlanSpec 结构化需求的 dict（含 constraints/changed）
    - itinerary_json: 最近一次生成的行程对象 {content, days[], spots[]}
    - destination / start_date / end_date: 便于按目的地的快速检索与展示
    每轮：加载 → 用 changed 应用增量 → 生成/修改 → 回写。
    """
    __tablename__ = "planning_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    session_key = Column(String(64), nullable=False, index=True, default="main")

    plan_spec_json = Column(JSON, nullable=True)
    itinerary_json = Column(JSON, nullable=True)
    destination = Column(String(64), nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<PlanningSession {self.user_id} {self.session_key} {self.destination}>"