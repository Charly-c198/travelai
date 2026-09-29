"""Agent API 路由"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, AsyncSessionLocal
from app.agent.graph import run_travel_agent
from app.agent.streaming import stream_travel_agent
from app.agent.learn import learn_from_itinerary
from app.services.rate_limit import check_rate
from app.agent.memory import save_message, get_conversation_history, clear_conversation_history
from app.schemas.agent import (
    AgentMessageRequest,
    AgentMessageResponse,
    ChatHistoryResponse
)
from app.utils.auth import get_current_user
from app.models.user import User
import logging

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=AgentMessageResponse)
async def chat_with_agent(
    request: AgentMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await check_rate(str(current_user.id))
    """
    与旅行规划 Agent 对话

    用户输入旅行需求，Agent 返回完整的行程规划
    """
    try:
        # 保存用户消息
        await save_message(
            user_id=str(current_user.id),
            role="user",
            content=request.message,
            db=db
        )

        # 运行 Agent
        result = await run_travel_agent(
            user_id=str(current_user.id),
            user_message=request.message,
            context=request.context,
            db=db,
        )

        # 保存 AI 回复
        await save_message(
            user_id=str(current_user.id),
            role="assistant",
            content=result.get("response", ""),
            db=db,
            metadata={
                "intent": result.get("intent"),
                "itinerary": result.get("draft_itinerary")
            }
        )

        return AgentMessageResponse(
            message=result.get("response", ""),
            intent=result.get("intent"),
            suggested_actions=result.get("suggested_actions", []),
            itinerary=result.get("draft_itinerary"),
            weather_info=result.get("weather_info")
        )

    except Exception as e:
        logger.error(f"Agent 处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"Agent 处理失败: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(
    request: AgentMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    与旅行规划 Agent 流式对话（SSE）：快速前置阶段后，行程正文逐 token 输出。

    事件: status / token / done / error
    前置需要保存用户消息（进入流前用依赖会话完成）。
    """
    await check_rate(str(current_user.id))
    # 持久化用户消息
    await save_message(
        user_id=str(current_user.id),
        role="user",
        content=request.message,
        db=db,
    )

    async def event_gen():
        # 汇总完整回复，便于流结束后持久化 AI 消息
        full_content = ""
        last_itinerary = None
        knowledge_source = None
        destination = None
        start_date = None
        end_date = None
        saved_trip_id = None
        async for line in stream_travel_agent(
            user_id=str(current_user.id),
            user_message=request.message,
            context=request.context,
            db=db,
        ):
            # 从 data 行解析出事件，用于累计 assistant 文本与行程对象
            try:
                body = line[len("data: "):].strip()
                ev = json.loads(body)
                t = ev.get("type")
                if t == "token":
                    full_content += ev.get("payload", {}).get("text", "")
                elif t == "done":
                    full_content = ev.get("payload", {}).get("message") or full_content
                    last_itinerary = ev.get("payload", {}).get("itinerary")
                    knowledge_source = ev.get("payload", {}).get("knowledge_source")
                    destination = ev.get("payload", {}).get("destination")
                    start_date = ev.get("payload", {}).get("start_date")
                    end_date = ev.get("payload", {}).get("end_date")
                    saved_trip_id = ev.get("payload", {}).get("saved_trip_id")
            except Exception:
                pass
            yield line

        # 流结束后，用独立会话持久化 AI 回复（不依赖请求依赖生命周期）
        if full_content.strip():
            async with AsyncSessionLocal() as session:
                try:
                    await save_message(
                        user_id=str(current_user.id),
                        role="assistant",
                        content=full_content,
                        db=session,
                        metadata={
                            "itinerary": last_itinerary,
                            "destination": destination,
                            "start_date": start_date,
                            "end_date": end_date,
                            "saved_trip_id": saved_trip_id,
                        },
                    )
                except Exception as e:
                    logger.warning(f"保存流式 AI 回复失败: {e}")

        # 自学习：仅当"本地库缺失→LLM 通识生成"时，把行程回灌知识库，expanding 新城市覆盖。
        # fire-and-forget，绝不阻塞用户已看到的回复。
        if knowledge_source == "llm_knowledge" and last_itinerary and destination:
            try:
                asyncio.get_running_loop().create_task(
                    learn_from_itinerary(last_itinerary, destination)
                )
            except Exception as e:
                logger.warning(f"启动自学习任务失败: {e}")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # 关键：通知反向代理不要缓冲 SSE
        },
    )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取对话历史"""
    messages = await get_conversation_history(
        user_id=str(current_user.id),
        db=db,
        limit=limit,
        offset=offset
    )

    return ChatHistoryResponse(
        messages=messages,
        total=len(messages),
        has_more=len(messages) == limit
    )


@router.delete("/history")
async def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """清除对话历史"""
    count = await clear_conversation_history(
        user_id=str(current_user.id),
        db=db
    )

    return {"message": f"已清除 {count} 条对话记录"}

