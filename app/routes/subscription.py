from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import and_, delete, or_, select

from app.lib.db import get_session
from app.lib.dependency import auth
from app.lib.models import SlicedSubscription, Subscription, SubscriptionType, User

router = APIRouter(prefix="/sub", tags=["wehbook"])


@router.get(
    "/all", summary="Get all subscription of this user", operation_id="get_all_sub"
)
async def get_all(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(auth)],
) -> list[SlicedSubscription]:
    stm = select(Subscription).where(Subscription.user_id == user.id)
    subscriptions = (await session.execute(stm)).scalars()
    sliced_subs = [SlicedSubscription(**sub.model_dump()) for sub in subscriptions]
    return sliced_subs


class NewSubscription(BaseModel):
    events: Literal["all"] | list[str]
    headers: dict[str, Any] | None
    endpoint: str
    type: SubscriptionType


@router.post(
    "/",
    summary="Create new subscription",
    operation_id="new_sub",
    status_code=status.HTTP_201_CREATED,
)
async def new_sub(
    subscription: NewSubscription,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(auth)],
) -> dict[str, str | SlicedSubscription]:
    """
    Create new subscription

    ### `SubscriptionType` explain:
    - **compact** Only return the path of changed item.

        The response should look like this:
        ```json
        {
            "<item id>.<path>": ["<old_value>", "<new value>"]
        }
        ```

        Example:
        ```json
        {
            "1.ticket_cost.base_cost": ["15", "10"],
            "2.sale_percentage": ["18", "36"],
            "8.stock": ["67", "69],
        }
        ```

    - **full** Return the full changed item data

        The response should look like this:
        ```json
        {
            "<item id>": {
                "old": <old_data>,
                "new": <new_data>,
                "changes": ["<path>"]
            }
        }
        ```

        Example:
        ```json
        {
            "1": {
                "old": {
                    "id": 1,
                    "name": "A dummy item",
                    "limited": true,
                    "enabled": {
                        "enabled_au": true,
                        "enabled_ca": true,
                        "enabled_eu": true,
                    },
                    "ticket_cost": {
                        "base_cost": 1,
                        "au": 1,
                        "ca": 1,
                        "eu": 1,
                    }
                },
                "new": {
                    "id": 1,
                    "name": "Just a dummy item",
                    "limited": true,
                    "enabled": {
                        "enabled_au": true,
                        "enabled_ca": true,
                        "enabled_eu": true,
                    },
                    "ticket_cost": {
                        "base_cost": 4,
                        "au": 5,
                        "ca": 8,
                        "eu": 1,
                    }
                },
                "changes": [
                    "name",
                    "ticket_cost.base_cost",
                    "ticket_cost.au",
                    "ticket_cost.ca",
                ]
            }
        }
        ```

    ### Body: 
    ```json
    {
        "events": list[str] or "all",
        "headers": dict[str, str] or None,
        "endpoint": str,
        "type": ResponseType,
    }
    ```
    - **events** 
    
        List of listened event.

        Must be one of these:

        - `<item_id>`
        
        - `<item_id>.<path>`

        Endpoint will only be notified when one of the item in events changed

        Set to `all` to get notified of every item changes.

    - **headers** The header of request to the endpoint
    
    - **endpoint** The endpoint to be notified
    
    - **type** One of the mentioned above.

    ### Return:
    ```json
    {
        "message": "ok",
        "data": <Subscription data>
    }
    ```
    """
    stm = select(Subscription).where(
        and_(
            Subscription.user_id == user.id,
            Subscription.endpoint == subscription.endpoint,
        )
    )
    existed_sub = (await session.execute(stm)).scalar_one_or_none()
    if existed_sub:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"message": "subscription with the same endpoint existed"},
        )

    new_sub = Subscription(
        user_id=user.id,
        events=subscription.events,
        endpoint=subscription.endpoint,
        headers=subscription.headers,
        type=subscription.type,
    )
    session.add(new_sub)
    await session.commit()

    return {"message": "ok", "data": SlicedSubscription(**new_sub.model_dump())}


class UpdateSubscription(BaseModel):
    events: Literal["all"] | list[str] | None
    headers: dict[str, Any] | None
    endpoint: str | None
    type: SubscriptionType | None


@router.put("/", summary="Update subscription", operation_id="update_sub")
async def update_sub(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(auth)],
    new_sub: UpdateSubscription,
    id: str | None = None,
    endpoint: str | None = None,
):
    """
    Create new subscription

    Params:
    - **id** Subscription id
    - **endpoint** Subscription endpoint
    *Note* Either `id` or `endpoint` must be specified

    Body: New subscription data

    Return:
    ```json
    {
        "message": "ok",
        "data": <Subscription data>
    }
    ```
    """
    if id is None and endpoint is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"message": "either subscription id or endpoint must be specified"},
        )

    stm = select(Subscription).where(
        and_(
            Subscription.user_id == user.id,
            or_(Subscription.endpoint == endpoint, Subscription.id == id),
        )
    )
    try:
        old_sub = (await session.execute(stm)).scalar_one()
    except NoResultFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"message": "subscription not found"},
        )

    for key, _ in UpdateSubscription.model_fields.items():
        val = getattr(new_sub, key)
        if val is not None:
            setattr(old_sub, key, val)

    session.add(old_sub)
    await session.commit()

    return {"message": "ok", "data": SlicedSubscription(**old_sub.model_dump())}


@router.delete(
    "/",
    summary="Delete subscription",
    operation_id="delete_sub",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delelet_sub(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(auth)],
    id: str | None = None,
    endpoint: str | None = None,
):
    """
    Delete subscription

    Params:
    - **id** Subscription id
    - **endpoint** Subscription endpoint
    *Note* Either `id` or `endpoint` must be specified

    Return
    ```
    None
    ```
    """
    if id is None and endpoint is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"message": "either subscription id or endpoint must be specified"},
        )
    stm = delete(Subscription).where(
        and_(
            Subscription.user_id == user.id,
            or_(Subscription.endpoint == endpoint, Subscription.id == id),
        )
    )
    await session.execute(stm)
    await session.commit()
