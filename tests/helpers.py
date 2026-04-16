from typing import Any


def expect_dict(data: Any):
    assert type(data) is dict, f"expect response is a dict, got {type(data)}"

def expect_message_ok(data: Any):
    expect_dict(data)
    expect_field(data, "message", str, "ok")


def expect_field[T: Any](data: Any, key: str, type_: type[T], val: T | None = None):
    expect_dict(data)
    assert key in data, f"expect a '{key}' field in response"
    assert type(data[key]) is type_, (
        f"expect type of data['{key}'] is a {str(type_)}, " + f"got {type(data[key])}"
    )
    if val:
        assert data[key] == val, f"expect data[{key}] is '{val}', got '{data[key]}'"


def expect_http_error(data: Any, error_msg: str):
    expect_dict(data)
    assert "detail" in data, "expect a 'detail' field in response"
    assert type(data["detail"]) is dict, (
        f"expect type of data['detail'] is a dict, got {type(data['detail'])}"
    )
    assert "message" in data["detail"], "expect a 'message' field in data['detail']"
    assert type(data["detail"]["message"]) is str, (
        "expect type of data['detail']['message'] is a str, "
        + f"got {type(data['detail']['message'])}"
    )
    assert data["detail"]["message"] == error_msg, (
        f"expect data['detail']['message'] is '{error_msg}', "
        + f"got '{data['detail']['message']}'"
    )


def expect_got[T: Any](expect: T, got: T):
    assert expect == got, f"expect status {expect}, got {got}"
