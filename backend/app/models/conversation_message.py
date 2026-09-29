"""对话消息数据模型"""
from sqlalchemy import Column, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.database import Base


class ConversationMessage(Base):
    """对话消息（用于持久化 Agent 对话历史）"""
    __tablename__ = "conversation_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    role = Column(String(20), nullable=False)  # user / assistant / system
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict)  # 附加元数据（意图、行程等）

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<ConversationMessage {self.role}: {self.content[:20]}...>"