"""对话记忆：会话消息的持久化存取"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_message import ConversationMessage


def _to_uuid(user_id: str) -> UUID:
    """将 user_id（str 或 UUID）转为 UUID 对象，匹配 UUID 列的绑定类型"""
    return user_id if isinstance(user_id, UUID) else UUID(str(user_id))


async def save_message(
    user_id: str,
    role: str,
    content: str,
    db: AsyncSession,
    metadata: Optional[Dict[str, Any]] = None,
) -> ConversationMessage:
    """保存一条对话消息"""
    message = ConversationMessage(
        user_id=_to_uuid(user_id),
        role=role,
        content=content,
        metadata_json=metadata or {},
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def get_conversation_history(
    user_id: str,
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """获取用户的对话历史（按时间倒序，返回列表头为最新）"""
    user_uuid = _to_uuid(user_id)
    stmt = (
        select(ConversationMessage)
        .where(ConversationMessage.user_id == user_uuid)
        .order_by(ConversationMessage.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    # 反转回时间正序，方便前端展示
    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "timestamp": m.created_at,
            "metadata": m.metadata_json,
        }
        for m in reversed(messages)
    ]


async def clear_conversation_history(user_id: str, db: AsyncSession) -> int:
    """清除用户全部对话历史，返回删除条数"""
    user_uuid = _to_uuid(user_id)
    stmt = delete(ConversationMessage).where(ConversationMessage.user_id == user_uuid)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0