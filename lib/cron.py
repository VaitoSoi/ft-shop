from asyncio import CancelledError, sleep
from copy import deepcopy
from operator import attrgetter
from typing import Any

from aiohttp import ClientSession, ContentTypeError
from pydantic import BaseModel
from sqlmodel import SQLModel, select

from lib.env import INTERVAL, TOKEN

from .db import session_maker
from .models import (
    Changes as DBChanges,
    ShopItem,
    Subscription,
    SubscriptionResponse,
    SubscriptionType,
)


class Changes(BaseModel):
    old: ShopItem
    new: ShopItem
    changes: list[str]

async def cron():
    try:
        await job()
        await sleep(INTERVAL)
    except CancelledError:
        return


old_data: dict[int, ShopItem] = {}


async def job():
    # Fetch all subscription
    async with session_maker() as session:
        subscriptions = (await session.execute(select(Subscription))).scalars()

    # Get new data
    new_data: list[ShopItem] = []
    async with ClientSession(
        base_url="https://flavortown.hackclub.com/api/v1/",
        headers={
            "Authorization": f"Bearer {TOKEN}"
        }
    ) as session:
        async with session.get("/store") as response:
            global old_data
            data: list[ShopItem] = [
                ShopItem.model_validate(item) for item in await response.json()
            ]
            if len(old_data) == 0:
                for val in data:
                    old_data[val.id] = val
                return

            new_data = data

    # Compute changes
    submit_to_db: list[SQLModel] = []
    for new_val in new_data:
        old_val = old_data[new_val.id]
        changes = diff(old_val, new_val)
        if not len(changes):
            continue

        item_changes = Changes(old=old_val, new=new_val, changes=changes)
        submit_to_db.append(DBChanges(**item_changes.model_dump()))

        compact_changes: dict[str, tuple[Any, Any]] = {}
        for change in changes:
            val_getter = attrgetter(change)
            compact_changes[change] = (val_getter(old_val), val_getter(new_val))

        affected_subscriptions = [
            sub
            for sub in subscriptions
            if sub.events == "all" or any([event in changes for event in sub.events])
        ]

        async with ClientSession() as session:
            for sub in affected_subscriptions:
                send_data = None
                if sub.type == SubscriptionType.full:
                    send_data = item_changes.model_dump()
                elif sub.type == SubscriptionType.compact:
                    send_data = compact_changes
                async with session.post(
                    sub.endpoint,
                    headers=sub.headers,
                    data=send_data
                ) as response:
                    res_data = None
                    try:
                        res_data = await response.json()
                    except ContentTypeError:
                        res_data = await response.text()
                    response_obj = SubscriptionResponse(
                        subscription_id=sub.id,
                        status_code=response.status,
                        header=dict(response.headers),
                        data=res_data
                    )
                    submit_to_db.append(response_obj)

    async with session_maker() as session:
        session.add_all(submit_to_db)
        await session.commit()

def diff[T: BaseModel](a: T, b: T) -> list[str]:
    changes: list[str] = []
    for key, fields in a.__class__.model_fields.items():
        before = getattr(a, key)
        after = getattr(b, key)

        if fields.annotation and issubclass(fields.annotation, BaseModel):
            for change in diff(before, after):
                changes.append(f"{key}.{change}")
            continue

        if diff_item(before, after):
            changes.append(key)

    return changes


def diff_item(a: Any, b: Any) -> bool:
    a_ = deepcopy(a)
    b_ = deepcopy(b)

    if isinstance(a_, list):
        if not isinstance(b_, list):
            return True
        for i in a_:
            if i not in b_:
                return True
            b_.remove(i)
        if len(b_):
            return True
    elif isinstance(a_, dict):
        if not isinstance(b_, dict):
            return True
        for i in a_.keys():
            if i not in b_:
                return True
            if a_[i] != b_[i]:
                return True
            del b_[i]
        if len(b_):
            return True
    else:
        return a != b

    return False
