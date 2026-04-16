import os
from operator import attrgetter
from typing import Literal

import pytest
import pytest_asyncio
from aiohttp import ClientSession, ContentTypeError
from aioresponses import aioresponses
from aioresponses.compat import URL
from aioresponses.core import RequestCall
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import SQLModel

from app import app
from app.lib.cron import Changes, job, old_data
from app.lib.db import engine
from app.lib.env import BASE_URL
from app.lib.models import ShopItem


def compare_obj(a: dict, b: dict, _path: str = "") -> Literal[True] | str:
    for field in a.keys():
        current_path = f"{_path}.{field}"
        if field not in b:
            return current_path

        if type(a[field]) is dict:
            result = compare_obj(a[field], b[field], f"{_path}.{field}")
            if type(result) is str:
                return result

        if type(a[field]) is not type(b[field]) or a[field] != b[field]:
            return current_path

    return True


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup():
    # Wipe old key (if any)
    dict_keys = set(old_data.keys())
    for key in dict_keys:
        del old_data[key]

    async with engine.connect() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    with TestClient(app) as client:
        # Create user
        client.post("/user", json={"username": "vaito", "password": "vaito"})
        response = client.post(
            "/user/auth", json={"username": "vaito", "password": "vaito"}
        )

        data = response.json()
        client.headers.update({"Authorization": f"Bearer {data['token']}"})

        # Create client
        client.post(
            "/webhook",
            json={
                "events": "all",
                "headers": None,
                "endpoint": "http://example.com",
                "type": "full",
            },
        )

    yield

    async with engine.connect() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)


@pytest.mark.skipif(
    os.getenv("SKIP_SEND_WEBHOOK", "").lower() == "true", reason="found SKIP_SEND_WEBHOOK"
)
@pytest.mark.asyncio
@pytest.mark.order(after="tests/test_webhook.py::test_delete_webhook")
async def test_server_is_online():
    async with ClientSession(base_url=BASE_URL) as session:
        async with session.get("ping") as response:
            assert response.status == status.HTTP_200_OK, (
                f"expect code 200, got {response.status}, is this correct test server?"
            )
            assert await response.json() == "ok", (
                f"expect response 'ok', got {await response.text()}, is this correct test server?"
            )


@pytest.mark.skipif(
    os.getenv("SKIP_SEND_WEBHOOK", "").lower() == "true", reason="found SKIP_SEND_WEBHOOK"
)
@pytest.mark.asyncio
@pytest.mark.order(after="test_server_is_online")
async def test_send_webhook():
    with aioresponses(passthrough=[BASE_URL]) as mock:
        mock.post("http://example.com", status=200)

        # Run the script that send notification to webhook
        await job()

    history: list[ShopItem] = []
    async with ClientSession(base_url=BASE_URL) as session:
        async with session.get("history") as response:
            try:
                datas = await response.json()
            except ContentTypeError:
                assert False, f"expect json, got {await response.text()}"

            for item in datas.pop():
                try:
                    history.append(ShopItem.model_validate(item))
                except ValidationError:
                    assert False, f"expect a ShopItem model, got {item}"

    assert len(mock.requests.keys()), "expect 1 request, got none"
    assert ("POST", URL("http://example.com")) in mock.requests, "expect example domain in mock requests dict"
    requests: list[RequestCall] = mock.requests[
        ("POST", URL("http://example.com"))
    ]
    assert len(requests) == 1, f"expect 1 request, got {len(requests)}"

    request: list[dict] = requests.pop().kwargs["json"]
    for item in request:
        try:
            Changes.model_validate(item)
        except ValidationError:
            assert False, f"expect data is Changes model, got {item}"
        assert item["old"] is None, f"expect data 'old' field is null, got {item['old']}"
        assert type(item["changes"]) is list, (
            f"expect data 'changes' is a list, got {type(item['changes'])}"
        )
        try:
            item_new = ShopItem.model_validate(item["new"])
        except ValidationError:
            assert False, f"expect data field 'new' is ShopItem model, got {item['new']}"

        item_in_history = next(
            history_item for history_item in history if history_item.id == item_new.id
        )

        result = compare_obj(item_new.model_dump(), item_in_history.model_dump())
        if result is not True:
            getter = attrgetter(result)
            assert False, (
                f"expect item[{result}] is {getter(item_in_history)}, got {getter(item)}"
            )
