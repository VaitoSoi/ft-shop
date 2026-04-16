from asyncio import sleep

import pytest
import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app import app
from app.lib.db import engine
from tests.helpers import expect_field, expect_got, expect_http_error, expect_message_ok


@pytest_asyncio.fixture(scope="module")
async def client():
    async with engine.connect() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)

    with TestClient(app) as client:
        yield client

    async with engine.connect() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)


@pytest.mark.order(0)
def test_user(client: TestClient):
    response = client.post("/user", json={"username": "vaito", "password": "vaito"})
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_201_CREATED, response.status_code)

    expect_message_ok(data)


@pytest.mark.order(after="test_user")
def test_conflict_user(client: TestClient):
    response = client.post("/user", json={"username": "vaito", "password": "vaito"})
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_409_CONFLICT, response.status_code)

    expect_http_error(data, "username existed")


@pytest.mark.order(after="test_user")
def test_token_wrong_username(client: TestClient):
    response = client.post(
        "/user/auth", json={"username": "not_vaito", "password": "vaito"}
    )
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_404_NOT_FOUND, response.status_code)

    expect_http_error(data, "username not found")


@pytest.mark.order(after="test_user")
def test_token_wrong_password(client: TestClient):
    response = client.post(
        "/user/auth", json={"username": "vaito", "password": "wrong_password"}
    )
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_401_UNAUTHORIZED, response.status_code)

    expect_http_error(data, "wrong password")


@pytest.mark.order(after="test_user")
def test_create_token(client: TestClient, cache: pytest.Cache):
    response = client.post("/user/auth", json={"username": "vaito", "password": "vaito"})
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_200_OK, response.status_code)

    expect_message_ok(data)
    expect_field(data, "scheme", str, "Bearer")
    expect_field(data, "token", str)

    cache.set("token", data["token"])


@pytest.mark.order(after=["test_create_token"])
def test_validate_token(client: TestClient, cache: pytest.Cache):
    token = cache.get("token", "")
    assert token != "", "where is my token ._.?"

    response = client.get("/user", headers={"Authorization": f"Bearer {token}"})
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_200_OK, response.status_code)

    expect_field(data, "username", str, "vaito")


@pytest.mark.order(after=["test_create_token"])
def test_invalid_scheme(client: TestClient):
    response = client.get(
        "/user", headers={"Authorization": "Not_Bearer also_not_a_valid_token"}
    )
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_400_BAD_REQUEST, response.status_code)

    expect_http_error(data, "authorization scheme must be Bearer")


def test_not_found_token(client: TestClient):
    response = client.get(
        "/user", headers={"Authorization": "Bearer also_not_a_valid_token"}
    )
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_401_UNAUTHORIZED, response.status_code)

    expect_http_error(data, "token not found")


@pytest.mark.asyncio
async def test_expired_token(client: TestClient):
    token_response = client.post(
        "/user/auth?expire_time=0:00:01", json={"username": "vaito", "password": "vaito"}
    )

    await sleep(2)

    response = client.get(
        "/user", headers={"Authorization": f"Bearer {token_response.json()['token']}"}
    )
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_401_UNAUTHORIZED, response.status_code)

    expect_http_error(data, "token expired")


@pytest.mark.order(after=["test_create_token"])
def test_revoke_token(client: TestClient, cache: pytest.Cache):
    token = cache.get("token", "")
    assert token != "", "where is my token ._.?"

    response = client.delete("/user/token", headers={"Authorization": f"Bearer {token}"})

    expect_got(status.HTTP_204_NO_CONTENT, response.status_code)


@pytest.mark.order(after=["test_revoke_token"])
def test_revoked_token(client: TestClient, cache: pytest.Cache):
    token = cache.get("token", "")
    assert token != "", "where is my token ._.?"

    response = client.get("/user", headers={"Authorization": f"Bearer {token}"})
    data = response.json()
    print("response", data)

    expect_got(status.HTTP_401_UNAUTHORIZED, response.status_code)

    expect_http_error(data, "token not found")


@pytest.mark.order(after="test_user")
def test_delete_user(client: TestClient):
    token_response = client.post(
        "/user/auth", json={"username": "vaito", "password": "vaito"}
    )

    response = client.delete(
        "/user", headers={"Authorization": f"Bearer {token_response.json()['token']}"}
    )

    expect_got(status.HTTP_204_NO_CONTENT, response.status_code)
