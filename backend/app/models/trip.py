"""行程数据模型"""
from sqlalchemy import Column, String, Text, Date, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.database import Base


class Trip(Base):
    """行程模型"""
    __tablename__ = "trips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # 行程基本信息
    title = Column(String(200), nullable=False)
    destination = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    budget = Column(Integer, default=0)
    travelers = Column(Integer, default=1)

    # 状态与需求
    status = Column(String(20), default="planning")  # planning/confirmed/in_progress/completed/cancelled
    requirements = Column(JSON, default=dict)  # 旅行偏好
    generated_plan = Column(JSON)  # AI 生成的行程

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="trips")
    days = relationship("ItineraryDay", back_populates="trip", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="trip", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Trip {self.title}: {self.start_date} ~ {self.end_date}>"

    @property
    def duration_days(self) -> int:
        """行程天数"""
        return (self.end_date - self.start_date).days + 1


class ItineraryDay(Base):
    """每日行程"""
    __tablename__ = "itinerary_days"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id"), nullable=False, index=True)

    day_number = Column(Integer, nullable=False)  # 第几天
    date = Column(Date, nullable=False)
    theme = Column(String(100))  # 今日主题
    summary = Column(Text)  # 行程摘要
    weather_info = Column(JSON)  # 天气预报

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    trip = relationship("Trip", back_populates="days")
    spots = relationship("ItinerarySpot", back_populates="day", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ItineraryDay Day {self.day_number}: {self.theme}>"


class ItinerarySpot(Base):
    """行程中的景点"""
    __tablename__ = "itinerary_spots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    day_id = Column(UUID(as_uuid=True), ForeignKey("itinerary_days.id"), nullable=False, index=True)
    spot_id = Column(UUID(as_uuid=True), ForeignKey("spots.id"), nullable=False)

    order_index = Column(Integer, nullable=False)  # 顺序
    start_time = Column(String(10))  # 开始时间 HH:MM
    end_time = Column(String(10))  # 结束时间
    duration_minutes = Column(Integer, default=120)  # 游览时长
    transport_to_next = Column(String(100))  # 到下一站交通
    estimated_cost = Column(Integer, default=0)  # 预估费用
    notes = Column(Text)  # 备注

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    day = relationship("ItineraryDay", back_populates="spots")
    spot = relationship("Spot")

    def __repr__(self):
        return f"<ItinerarySpot {self.order_index}>"
