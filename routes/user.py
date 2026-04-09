from datetime import datetime, timedelta
from random import choices
from string import ascii_letters, digits
from typing import Annotated, Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, delete, select

from lib.db import get_session
from lib.dependency import auth
from lib.models import Token, User

router = APIRouter(prefix="/user", tags=["user"])
pass_hash = PasswordHasher()


class RequestUser(BaseModel):
    username: str
    password: str


@router.post(
    "/",
    summary="Create new user",
    operation_id="create_user",
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: RequestUser,
) -> dict[str, str]:
    """
    Create user

    Params:
    - **user** Username and password

    Return:
    ```json
    {
        "message": "ok",
    }
    ```
    """

    stm = select(User).where(User.username == user.username)
    existed_user = (await session.execute(stm)).scalar_one_or_none()
    if existed_user is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"message": "username existed"}
        )

    db_user = User(username=user.username, password=pass_hash.hash(user.password))
    session.add(db_user)
    await session.commit()

    return {"message": "ok"}

class AuthResponse(BaseModel):
    message: Literal["ok"] = Field(default="ok")
    scheme: Literal["bearer"] = Field(default="bearer")
    token: str

@router.post(
    "/auth",
    summary="Get token",
    operation_id="auth",
)
async def create_token(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: RequestUser,
    expire_time: timedelta | None = None,
) -> AuthResponse:
    """
    Create auth token

    Params:
    - **user** Username and password
    - **expire_time** Time to expire token

    Return:
    ```json
    {
        "message": "ok",
        "scheme": "Bearer",
        "token": <your token>
    }
    ```
    """

    try:
        stm = select(User).where(User.username == user.username)
        db_user = (await session.execute(stm)).scalar_one()
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "username not found"},
        )

    hashed_password = db_user.password
    try:
        pass_hash.verify(hashed_password, user.password)
    except VerifyMismatchError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail={"message": "wrong password"}
        )

    token = "".join(choices(digits + ascii_letters, k=128))
    token_obj = Token(user_id=db_user.id, token=token)
    if expire_time:
        token_obj.expired_at = datetime.now() + expire_time
    session.add(token_obj)
    await session.commit()

    return AuthResponse(token=token)


@router.delete(
    "/",
    summary="Delete this user",
    operation_id="delete_user",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(auth)],
):
    """
    Delete current user

    Return
    ```
    None
    ```
    """
    await session.execute(delete(User).where(col(User.id) == user.id))
    await session.commit()

