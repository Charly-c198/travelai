"""景点数据模型"""
from sqlalchemy import Column, String, Float, Integer, Text, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.database import Base


class Spot(Base):
    """景点模型"""
    __tablename__ = "spots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False, index=True)
    name_en = Column(String(200), nullable=True)
    city = Column(String(100), nullable=False, index=True)
    country = Column(String(100), nullable=True)
    category = Column(String(50), nullable=True, index=True)
    address = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    rating = Column(Float, default=0)
    ticket_info = Column(JSON, default=dict)
    description = Column(Text, nullable=True)
    recommend_duration = Column(Integer, default=120)
    tags = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    itinerary_spots = relationship("ItinerarySpot", back_populates="spot")

    def __repr__(self):
        return f"<Spot {self.name}: {self.city}>"