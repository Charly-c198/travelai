"""预订数据模型"""
from sqlalchemy import Column, String, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.database import Base


class Booking(Base):
    """预订模型（机票/酒店等）"""
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False, index=True)

    type = Column(String(20), nullable=False)  # flight / hotel
    status = Column(String(20), default="pending")  # pending/confirmed/cancelled
    details = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    trip = relationship("Trip", back_populates="bookings")

    def __repr__(self):
        return f"<Booking {self.type}: {self.status}>"