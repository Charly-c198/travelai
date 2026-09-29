"""Agent 相关 Pydantic 模型"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class AgentMessageRequest(BaseModel):
    """Agent 消息请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    context: Optional[Dict[str, Any]] = Field(default={}, description="上下文数据")


class AgentMessageResponse(BaseModel):
    """Agent 消息响应"""
    message: str = Field(..., description="AI 回复内容")
    intent: Optional[str] = Field(default=None, description="识别的意图")
    suggested_actions: List[str] = Field(default=[], description="建议的操作")
    itinerary: Optional[Dict[str, Any]] = Field(default=None, description="生成的行程")
    weather_info: Optional[Dict[str, Any]] = Field(default=None, description="天气信息")


class ChatMessage(BaseModel):
    """对话消息"""
    id: str
    role: str  # "user" / "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class ChatHistoryResponse(BaseModel):
    """对话历史响应"""
    messages: List[ChatMessage]
    total: int
    has_more: bool

