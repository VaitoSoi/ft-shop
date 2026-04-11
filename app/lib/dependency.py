from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.lib.db import get_session
from app.lib.models import Token


async def auth(
    session: Annotated[AsyncSession, Depends(get_session)],
    Authorization: Annotated[str, Header()],
):
    scheme, token = Authorization.split(" ")

    if scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "authorization scheme must be Bearer"},
        )

    stm = select(Token).where(Token.token == token)
    try:
        token_obj =(await session.execute(stm)).scalar_one()
    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "token not found"},
        )
    
    if token_obj.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "token revoked"},
        )

    if token_obj.expired_at < datetime.now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "token expired"},
        )

    return token_obj.user
