"""LLM 调用指标采集：记录每次生成的延迟/Token/成本估算。

- 通过 contextvar 把"当前请求的 user_id/destination"传给 LLM 客户端包装器，
  让埋在 client 里的 record 知道归属（跨节点/跨流式生成共享）。
- 持久化 best-effort（fire-and-forget），绝不阻塞主流程。
- Token/成本均为估算（字符数×系数 + 配置单价），用于"单会话净贡献"复盘，非计费。
"""
import asyncio
import contextvars
import logging
import math
import time
from typing import Dict, Optional
from uuid import UUID

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.generation_metric import GenerationMetric

logger = logging.getLogger(__name__)
settings = get_settings()

_ctx: contextvars.ContextVar[Dict] = contextvars.ContextVar("agent_metrics_ctx", default={})


def set_metrics_ctx(user_id=None, destination=None):
    """在 Agent 入口设置当前请求的归属上下文（best-effort，随时可覆盖）。"""
    old = _ctx.get()
    merged = dict(old)
    if user_id is not None:
        merged["user_id"] = user_id
    if destination is not None:
        merged["destination"] = destination
    _ctx.set(merged)


def reset_metrics_ctx():
    _ctx.set({})


def _tokens(chars: int) -> int:
    return max(0, int(chars * settings.CHARS_PER_TOKEN))


def _cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * settings.LLM_PRICE_INPUT + completion_tokens * settings.LLM_PRICE_OUTPUT) / 1000


def record_generation(
    kind: str,
    model: str,
    prompt_chars: int,
    completion_chars: int,
    first_token_ms: int,
    total_ms: int,
) -> None:
    """异步落库（fire-and-forget）。"""
    try:
        ctx = _ctx.get()
        uid = ctx.get("user_id")
        if not uid:
            return  # 非用户触发的调用（如后台任务）不记
        try:
            user_uuid = UUID(str(uid))
        except (ValueError, AttributeError):
            return
        pt = _tokens(prompt_chars)
        ct = _tokens(completion_chars)
        metric = GenerationMetric(
            user_id=user_uuid,
            kind=kind,
            model=model,
            destination=(ctx.get("destination") or "")[:50],
            prompt_tokens=pt,
            completion_tokens=ct,
            first_token_ms=first_token_ms,
            total_ms=total_ms,
            cost=_cost(pt, ct),
        )
        asyncio.get_running_loop().create_task(_persist(metric))
    except Exception as e:
        logger.warning(f"记录生成指标失败: {e}")


async def _persist(metric: GenerationMetric):
    try:
        async with AsyncSessionLocal() as db:
            db.add(metric)
            await db.commit()
    except Exception as e:
        logger.warning(f"持久化生成指标失败: {e}")


def percentile(values, p: float) -> Optional[int]:
    """计算百分位（毫秒整数）；空返回 None。"""
    if not values:
        return None
    sorted_v = sorted(values)
    idx = int(math.ceil(p / 100.0 * len(sorted_v))) - 1
    idx = max(0, min(idx, len(sorted_v) - 1))
    return int(sorted_v[idx])
