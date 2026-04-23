from asyncio import CancelledError, Lock, Task, create_task, gather
from operator import attrgetter
from typing import Any

from aiohttp import ClientSession, ClientTimeout, ContentTypeError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from pydantic import BaseModel
from sqlmodel import SQLModel, select

from app.lib.env import (
    BASE_URL,
    INTERVAL,
    MAX_INSTANCES,
    NOTIFY_WHEN_EMPTY,
    TIMEOUT,
    TOKEN,
)
from app.lib.utils import diff, flatten_obj

from .db import session_maker
from .models import (
    Changes as DBChanges,
    ShopItem,
    Subscription,
    SubscriptionResponse,
    SubscriptionType,
)


class Changes(BaseModel):
    old: ShopItem | None
    new: ShopItem | None
    changes: list[str]


old_data: dict[int, ShopItem] = {}

scheduler = AsyncIOScheduler()
lock = Lock()


@scheduler.scheduled_job(IntervalTrigger(seconds=INTERVAL), max_instances=MAX_INSTANCES)
async def job():
    try:
        await lock.acquire()
        await job_()
        lock.release()
    except KeyboardInterrupt, CancelledError:
        return
    except Exception as e:
        print(e)


async def job_():
    global old_data

    # Get new data
    new_data: list[ShopItem] = []
    async with ClientSession(
        base_url=BASE_URL, headers={"Authorization": f"Bearer {TOKEN}"}
    ) as session:
        async with session.get("store", timeout=ClientTimeout(total=TIMEOUT)) as response:
            try:
                ft_data: list[ShopItem] = [
                    ShopItem.model_validate(item) for item in await response.json()
                ]
                if len(old_data) == 0:
                    for val in ft_data:
                        old_data[val.id] = val

                    if NOTIFY_WHEN_EMPTY:
                        await _notify_changed_item({}, ft_data)

                    return

                new_data = ft_data

            except ContentTypeError as error:
                raise ValueError(f"expect json, got '{await response.text()}'") from error

    await _notify_changed_item(old_data, new_data)


async def _notify_changed_item(old_data: dict, new_data: list[ShopItem]):
    # Fetch all subscription
    sub_dicts: dict[str, Subscription] = {}
    async with session_maker() as session:
        subscriptions = (await session.execute(select(Subscription))).scalars().all()
        sub_dicts = {sub.id: sub for sub in subscriptions}

    # Compute changes
    touched: list[int] = []
    submit_to_db: list[SQLModel] = []
    notifications: dict[str, Any] = {}
    for new_val in new_data:
        # Whole new items
        if new_val.id not in old_data:
            flattened_data = flatten_obj(new_val.model_dump())
            changes = list(flattened_data.keys())

            item_changes = Changes(old=None, new=new_val, changes=changes)
            compact_changes: dict[str, tuple[Any, Any]] = {}
            for change in changes:
                compact_changes[change] = (None, flattened_data[change])

        # Updated item
        else:
            old_val = old_data[new_val.id]
            changes = diff(old_val, new_val)
            if not len(changes):
                touched.append(new_val.id)
                continue

            item_changes = Changes(old=old_val, new=new_val, changes=changes)

            compact_changes: dict[str, tuple[Any, Any]] = {}
            for change in changes:
                val_getter = attrgetter(change)
                compact_changes[change] = (val_getter(old_val), val_getter(new_val))

        touched.append(new_val.id)
        submit_to_db.append(DBChanges(**item_changes.model_dump()))
        affected_subscriptions = [
            sub
            for sub in subscriptions
            if sub.events == "all" or any([event in changes for event in sub.events])
        ]

        for sub in affected_subscriptions:
            if sub.type == SubscriptionType.full:
                send_data = item_changes.model_dump(by_alias=True)
                notifications.setdefault(sub.id, []).append(send_data)

            elif sub.type == SubscriptionType.compact:
                send_data = notifications.setdefault(sub.id, {})
                for path, change in compact_changes.items():
                    send_data[f"{new_val.id}.{path}"] = change

            else:
                continue

        # Assign update to cache
        old_data[new_val.id] = new_val

    # Remove deleted item
    remove_keys: list[int] = []
    for id, data in old_data.items():
        if id in touched:
            continue

        flattened_data = flatten_obj(data.model_dump())
        changes = list(flattened_data.keys())

        item_changes = Changes(old=data, new=None, changes=changes)
        compact_changes: dict[str, tuple[Any, Any]] = {}
        for change in changes:
            compact_changes[change] = (None, flattened_data[change])

        submit_to_db.append(DBChanges(**item_changes.model_dump()))
        affected_subscriptions = [
            sub
            for sub in subscriptions
            if sub.events == "all" or any([event in changes for event in sub.events])
        ]

        for sub in affected_subscriptions:
            if sub.type == SubscriptionType.full:
                send_data = item_changes.model_dump(by_alias=True)
                notifications.setdefault(sub.id, []).append(send_data)

            elif sub.type == SubscriptionType.compact:
                send_data = notifications.setdefault(sub.id, {})
                for path, change in compact_changes.items():
                    send_data[f"{data.id}.{path}"] = change

            else:
                continue

        remove_keys.append(id)

    for key in remove_keys:
        del old_data[key]

    # Notify user
    for sub_id, datas in notifications.items():
        sub = sub_dicts[sub_id]
        async with ClientSession(sub.endpoint) as session:
            async with session.post(
                url="",
                headers=sub.headers,
                json=datas,
                timeout=ClientTimeout(total=TIMEOUT),
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
                    data=res_data,
                )
                submit_to_db.append(response_obj)

    # Add everything to DB
    async with session_maker() as session:
        session.add_all(submit_to_db)
        await session.commit()
