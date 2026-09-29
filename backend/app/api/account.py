"""账户 API：额度/订阅查看与升级（支付暂为占位）。"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.quota_service import get_usage, set_plan
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/account", tags=["Account"])


class UpgradeIn(BaseModel):
    plan: str = "pro"


@router.get("/usage")
async def usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """今日生成额度使用情况。"""
    u = await get_usage(db, current_user.id)
    return {"user_id": str(current_user.id), **u}


@router.post("/upgrade")
async def upgrade(
    data: UpgradeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """升级/切权益（目前为占位：支付网关待接）。"""
    plan = await set_plan(db, current_user.id, data.plan)
    return {"ok": True, "plan": plan}