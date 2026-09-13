from fastapi import APIRouter

from app.controllers import user_controller
from app.dependencies.auth_dependency import CurrentUser
from app.schemas.user_schema import UserProfileResponse

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(current_user: CurrentUser):
    return await user_controller.get_profile(current_user)
