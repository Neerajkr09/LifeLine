from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.database import get_database
from app.core.security import decode_access_token
from app.models.user_model import Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=True)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncIOMotorDatabase, Depends(get_database)],
) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception

    try:
        oid = ObjectId(user_id)
    except (InvalidId, TypeError):
        raise credentials_exception

    user = await db.users.find_one({"_id": oid, "is_deleted": False})
    if user is None:
        raise credentials_exception
    if user.get("is_banned"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ACCOUNT IS BANNED DUE TO SUSPECTED ACTIVITY!",
        )
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is deactivated.")

    return user


def require_role(*allowed_roles: Role):
    """Dependency factory enforcing role-based authorization on a route."""

    async def _dependency(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
        if current_user["role"] not in {r.value for r in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return _dependency


CurrentUser = Annotated[dict, Depends(get_current_user)]
