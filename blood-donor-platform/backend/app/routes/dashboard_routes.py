from typing import Annotated

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.controllers import dashboard_controller
from app.core.database import get_database
from app.dependencies.auth_dependency import require_role
from app.models.user_model import Role
from app.schemas.dashboard_schema import DonorDashboardStats, RecipientDashboardStats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/recipient", response_model=RecipientDashboardStats)
async def recipient_dashboard(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.RECIPIENT))],
):
    stats = await dashboard_controller.get_recipient_dashboard_stats(db, str(current_user["_id"]))
    return stats


@router.get("/donor", response_model=DonorDashboardStats)
async def donor_dashboard(
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
    current_user: Annotated[dict, Depends(require_role(Role.DONOR))],
):
    stats = await dashboard_controller.get_donor_dashboard_stats(db, current_user)
    return stats
