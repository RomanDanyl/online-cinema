from typing import Sequence, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_jwt_auth_manager
from database import UserModel, get_db, UserGroupEnum
from exceptions import BaseSecurityError
from security.interfaces import JWTAuthManagerInterface

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/accounts/login/")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserModel:
    """Return the authenticated user from a bearer access token.

    The dependency decodes the JWT access token, fetches the corresponding user,
    and validates that the account exists and is active. It raises appropriate
    HTTP errors when the token is invalid or the user cannot be used.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        )

    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )

    return user


def require_roles(allowed_roles: Sequence[UserGroupEnum]) -> Callable:
    """
    Return role checking dependency.
    """
    async def dependency(current_user: UserModel = Depends(get_current_user)) -> UserModel:
        if current_user.group.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource",
            )
        return current_user

    return dependency
