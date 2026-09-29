"""应用程序配置"""
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    APP_NAME: str = "TravelAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 数据库配置（开发默认 SQLite + aiosqlite 异步驱动）
    DATABASE_URL: str = "sqlite+aiosqlite:///./travelai.db"
    # PostgreSQL 生产环境使用（通过环境变量 DATABASE_URL 切换）
    # DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/travelai"

    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT 配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # LLM 配置（默认 qwen；也可在 .env 中覆盖）
    LLM_PROVIDER: str = "qwen"  # openai / deepseek / qwen
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 2000

    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    QWEN_API_KEY: Optional[str] = None
    QWEN_MODEL: str = "qwen-max"
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # RAG 配置
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    VECTOR_STORE_TYPE: str = "chroma"  # chroma / faiss
    VECTOR_STORE_PATH: str = "./data/vectorstore"

    # 外部 API 配置
    AMAP_API_KEY: Optional[str] = None  # 高德地图
    WEATHER_API_KEY: Optional[str] = None  # 天气 API
    FLIGHT_API_KEY: Optional[str] = None  # 机票 API
    # 机票（CPS 落地页深链）：
    # RollingGo 已取消飞行 MCP，改用"携程/去哪儿移动端搜索深链 + 渠道参数"做预订推进（方案A：无实时价格）。
    FLIGHT_DEFAULT_ORIGIN: str = "北京"  # 出发地（行程未存出发地时默认；可换成渠道默认城市）
    # 深链模板；{from}{to}{date} 为占位，替换成你自己的携程联盟/去哪儿 CPS 链接后带渠道参数。
    FLIGHT_BOOKING_URL_TEMPLATE: str = (
        "https://m.ctrip.com/webapp/flight/search/oneway?dcity={from}&acity={to}&ddate={date}"
    )
    # 目的地动态配图（Unsplash）。key 只存服务端，经 /api/v1/images 代理下发压缩图。
    UNSPLASH_API_KEY: Optional[str] = None
    # Wikipedia 实体配图（方案B）：zh.wikipedia.org 在大陆被墙，默认关闭；
    # 海外/代理环境可设 true，命中则用实体权威主图，否则降级 Qwen 消歧 + Unsplash。
    WIKIPEDIA_ENABLED: bool = False
    # RollingGo（道旅）MCP：酒店预订。两把地址已保留（flight 已停更，不再用）
    ROLLINGGO_HOTEL_MCP_URL: str = "https://mcp.rollinggo.cn/mcp"
    ROLLINGGO_FLIGHT_MCP_URL: str = "https://mcp.rollinggo.cn/mcp/flight"
    ROLLINGGO_API_KEY: Optional[str] = None

    # CORS 配置
    CORS_ORIGINS: list = ["http://localhost:5173", "http://localhost:3000"]

    # 订阅/容量控制：每日高质量生成免费额度（Pro 更高）
    FREE_DAILY_GENERATIONS: int = 3
    PRO_DAILY_GENERATIONS: int = 100

    # LLM 成本估算（元/千 token；为估算值，请按实际账单校准）
    LLM_PRICE_INPUT: float = 0.0008
    LLM_PRICE_OUTPUT: float = 0.002
    # 字符→token 估算系数（中文为主约 0.7 token/字）
    CHARS_PER_TOKEN: float = 0.7

    class Config:
        # 基于 config.py 所在目录定位 .env，避免依赖当前工作目录
        env_file = str(Path(__file__).resolve().parent / ".env")
        case_sensitive = True

    def model_post_init(self, __context) -> None:
        # 以 backend 根目录（config.py 的父目录的父目录）为基准，将相对路径固定为绝对路径，
        # 避免数据库/向量库位置随启动目录漂移（否则不同目录启动会读到不同 travelai.db）
        base = Path(__file__).resolve().parent.parent
        # 数据库：仅当是相对 sqlite 路径时才改写（PostgreSQL 等绝对 URL 不处理）
        if self.DATABASE_URL.startswith("sqlite"):
            prefix, sep, rel = self.DATABASE_URL.partition("///")
            if sep and rel and not Path(rel).is_absolute():
                self.DATABASE_URL = f"{prefix}///{(base / Path(rel)).resolve().as_posix()}"
        # 向量库路径
        if self.VECTOR_STORE_PATH and not Path(self.VECTOR_STORE_PATH).is_absolute():
            self.VECTOR_STORE_PATH = str((base / Path(self.VECTOR_STORE_PATH)).resolve())


@lru_cache()
def get_settings() -> Settings:
    """获取配置（单例）"""
    return Settings()
