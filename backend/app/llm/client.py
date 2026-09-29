"""LLM 客户端配置"""
import time
from functools import lru_cache
from typing import AsyncIterator

from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.llm_metrics import record_generation

settings = get_settings()

# 各提供商的 API 配置映射（DeepSeek/Qwen 均兼容 OpenAI Chat Completions 协议）
_PROVIDER_CONFIG = {
    "openai": {
        "base_url": settings.OPENAI_BASE_URL,
        "api_key": settings.OPENAI_API_KEY,
        "model": settings.OPENAI_MODEL,
    },
    "deepseek": {
        "base_url": settings.DEEPSEEK_BASE_URL,
        "api_key": settings.DEEPSEEK_API_KEY,
        "model": settings.DEEPSEEK_MODEL,
    },
    "qwen": {
        "base_url": settings.QWEN_BASE_URL,
        "api_key": settings.QWEN_API_KEY,
        "model": settings.QWEN_MODEL,
    },
}


def _count_chars(text) -> int:
    """统计输入/输出文本字符数（兼容 langchain 的 str 或 content 块列表）。"""
    if isinstance(text, str):
        return len(text)
    if isinstance(text, list):
        return sum(len(getattr(p, "text", "") or "") for p in text)
    if text is None:
        return 0
    return len(str(text))


class _TrackedLLM:
    """给 ChatOpenAI 加一层透明代理：记录每次调用的首 token/总耗时/字符量→token/成本估算。

    仅透传 ainvoke / astream（项目内仅使用这两个），其余属性原样透传到底层。
    """

    def __init__(self, inner: ChatOpenAI, model: str):
        self._inner = inner
        self._model = model

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def ainvoke(self, input, **kwargs):
        prompt_chars = _count_chars(input)
        t0 = time.monotonic()
        resp = await self._inner.ainvoke(input, **kwargs)
        total_ms = int((time.monotonic() - t0) * 1000)
        record_generation(
            "invoke", self._model, prompt_chars,
            _count_chars(getattr(resp, "content", "")),
            total_ms, total_ms,
        )
        return resp

    def astream(self, input, **kwargs) -> AsyncIterator:
        return self._astream(self._inner.astream(input, **kwargs), input)

    async def _astream(self, agen, input) -> AsyncIterator:
        prompt_chars = _count_chars(input)
        t0 = time.monotonic()
        first_ms = None
        completion_chars = 0
        try:
            async for chunk in agen:
                if first_ms is None:
                    first_ms = int((time.monotonic() - t0) * 1000)
                completion_chars += _count_chars(getattr(chunk, "content", ""))
                yield chunk
        finally:
            total_ms = int((time.monotonic() - t0) * 1000)
            record_generation(
                "stream", self._model, prompt_chars, completion_chars,
                first_ms or total_ms, total_ms,
            )


@lru_cache()
def get_llm_client() -> ChatOpenAI:
    """
    获取 LLM 客户端（单例）

    根据 config 中的 LLM_PROVIDER 选择 openai / deepseek / qwen 三家之一。
    三家均通过 OpenAI 兼容协议调用，统一使用 ChatOpenAI。
    返回带指标采集的透明代理（getattr 透传，行为与 ChatOpenAI 一致）。
    """
    provider = settings.LLM_PROVIDER

    if provider not in _PROVIDER_CONFIG:
        raise ValueError(
            f"未知的 LLM_PROVIDER: {provider}，可选值为 {list(_PROVIDER_CONFIG.keys())}"
        )

    conf = _PROVIDER_CONFIG[provider]
    api_key = conf["api_key"]

    if not api_key:
        raise ValueError(f"未配置 {provider} 的 API Key，请检查 .env 或环境变量")

    inner = ChatOpenAI(
        model=conf["model"],
        api_key=api_key,
        base_url=conf["base_url"],
        temperature=settings.OPENAI_TEMPERATURE,
        max_tokens=settings.OPENAI_MAX_TOKENS,
    )
    return _TrackedLLM(inner, conf["model"])


def get_llm_model_name() -> str:
    """返回当前实际使用的模型名（便于日志/调试）"""
    provider = settings.LLM_PROVIDER
    return _PROVIDER_CONFIG.get(provider, {}).get("model", "unknown")


def get_llm_provider() -> str:
    """返回当前 LLM 提供商"""
    return settings.LLM_PROVIDER