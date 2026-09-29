"""数据库初始化脚本：创建全部表"""
import asyncio
import sys
import os

# 确保运行时能以 backend 为项目根导入 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import init_db, engine, Base
from app import models  # noqa: F401  确保所有模型被收集


async def main():
    print("📦 正在初始化数据库表...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建完成")


if __name__ == "__main__":
    asyncio.run(main())