import pytest
import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import SQLModel

from app import app
from app.lib.db import engine
from app.lib.models import SlicedSubscription
from tests.helpers import expect_field, expect_got, expect_http_error, expect_message_ok


@pytest_asyncio.fixture(scope="module")
async def client():
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

        yield client

    async with engine.connect() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)


def test_get_all_but_empty(client: TestClient):
    response = client.get("/webhook/all")
    data = response.json()
    print(data)

    expect_got(status.HTTP_200_OK, response.status_code)

    assert type(data) is list, f"expect response is a list, got {type(data)}"
    assert len(data) == 0, f"expect empty list, got {data}"

@pytest.mark.order(after="test_get_all_but_empty")
def test_create_webhook(client: TestClient):
    response = client.post(
        "/webhook",
        json={
            "events": "all",
            "headers": None,
            "endpoint": "http://example.com",
            "type": "full",
        },
    )
    data = response.json()
    print(data)

    expect_got(status.HTTP_201_CREATED, response.status_code)

    expect_message_ok(data)
    expect_field(data, "data", dict)
    try:
        webhook_data = SlicedSubscription.model_validate(data["data"])

    except ValidationError:
        pytest.fail("data['data'] is not a SlicedSubscription model")

    assert webhook_data.events == "all", "incorrect data"
    assert webhook_data.headers is None, "incorrect data"
    assert webhook_data.endpoint == "http://example.com", "incorrect data"
    assert webhook_data.type.value == "full", "incorrect data"


@pytest.mark.order(after="test_create_webhook")
def test_get_all(client: TestClient):
    response = client.get("/webhook/all")
    data = response.json()
    print(data)

    expect_got(status.HTTP_200_OK, response.status_code)

    assert type(data) is list, f"expect response is a list, got {type(data)}"

    for ind, item in enumerate(data):
        assert type(item) is dict, f"expect data[{ind}] is a dict, got {type(item)}"
        try:
            SlicedSubscription.model_validate(data[ind])

        except ValidationError:
            pytest.fail(f"data[{ind}] is not a SlicedSubscription model")


def test_invalid_update_webhook(client: TestClient):
    response = client.put(
        "/webhook", json={"endpoint": "http://shouldnt-be-updated.huh"}
    )
    data = response.json()
    print(data)

    expect_got(status.HTTP_400_BAD_REQUEST, response.status_code)
    expect_http_error(data, "either subscription id or endpoint must be specified")
    

@pytest.mark.order(after="test_create_webhook")
def test_update_webhook(client: TestClient):
    response = client.put(
        "/webhook?endpoint=http://example.com", json={"endpoint": "https://example.com"}
    )
    data = response.json()
    print(data)

    expect_got(status.HTTP_200_OK, response.status_code)

    expect_message_ok(data)
    expect_field(data, "data", dict)
    try:
        webhook_data = SlicedSubscription.model_validate(data["data"])

    except ValidationError:
        pytest.fail("data['data'] is not a SlicedSubscription model")

    assert webhook_data.events == "all", "incorrect data"
    assert webhook_data.headers is None, "incorrect data"
    assert webhook_data.endpoint == "https://example.com", "incorrect data"
    assert webhook_data.type.value == "full", "incorrect data"


def test_update_unknown_webhook(client: TestClient):
    response = client.put(
        "/webhook?endpoint=http://i-dunnu.huh", json={"endpoint": "http://shouldnt-be-updated.huh"}
    )
    data = response.json()
    print(data)

    expect_got(status.HTTP_404_NOT_FOUND, response.status_code)
    expect_http_error(data, "subscription not found")


@pytest.mark.order(after="test_create_webhook")
def test_delete_webhook(client: TestClient):
    response = client.delete("/webhook?endpoint=https://example.com")

    expect_got(status.HTTP_204_NO_CONTENT, response.status_code)
