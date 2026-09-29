"""用户画像模型：沉淀旅行偏好（风格/目的地），用于个性化生成。"""
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True)

    # 最近/最常见旅行风格（relaxed/adventurous/family/...）
    travel_style = Column(String(32), default="")
    # 风格计数 {"relaxed": 3, "foodie": 1}
    travel_styles = Column(JSON, default=dict)
    # 去过的目的地（去重）
    destinations = Column(JSON, default=list)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserProfile {self.user_id} style={self.travel_style}>"