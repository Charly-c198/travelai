"""商业埋点表：记录 CPS 漏斗（曝光/点击/预订）等事件，支撑北极星"单会话净贡献"。"""
from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

from app.database import Base


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    # 事件类型：trip_view / booking_click / booking_success / chat_sent / ...
    event = Column(String(50), nullable=False, index=True)
    # 渠道：rollinggo_hotel / gaode / ...
    channel = Column(String(50), default="")
    trip_id = Column(UUID(as_uuid=True), nullable=True)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (Index("ix_tracking_event_time", "event", "created_at"),)

    def __repr__(self):
        return f"<TrackingEvent {self.event} channel={self.channel}>"