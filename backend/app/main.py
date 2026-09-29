"""FastAPI 应用入口"""
import os
import sys

# 确保以 backend 为根识别 app 包（支持直接运行本文件）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.api import agent as agent_api
from app.api import auth as auth_api
from app.api import trips as trips_api
from app.api import spots as spots_api
from app.api import hotels as hotels_api
from app.api import tracking as tracking_api
from app.api import account as account_api
from app.api import dashboard as dashboard_api
from app.api import flights as flights_api
from app.api import images as images_api

# 导入所有模型，确保 Base.metadata 收集全部表
from app import models  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    logger.info("🚀 正在初始化数据库...")
    await init_db()
    logger.info("✅ 数据库初始化完成")
    yield


# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_api.router)
app.include_router(agent_api.router)
app.include_router(trips_api.router)
app.include_router(trips_api.share_router)
app.include_router(spots_api.router)
app.include_router(hotels_api.router)
app.include_router(tracking_api.router)
app.include_router(account_api.router)
app.include_router(dashboard_api.router)
app.include_router(flights_api.router)
app.include_router(images_api.router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "message": "TravelAI 后端服务",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)