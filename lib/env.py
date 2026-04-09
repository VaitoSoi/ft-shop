from os import getenv

import python_ms as ms
from dotenv import load_dotenv

load_dotenv()


def require_env(var: str):
    val = getenv(var)
    if val is None:
        raise RuntimeError(f"env {var} is required")
    return val

DB_URL = require_env("DB_URL")
TOKEN = require_env("TOKEN")
INTERVAL = int(getenv("INTERVAL", "5"))
EXPIRE_TIME = getenv("EXPIRE_TIME")
EXPIRE_TIME = ms(EXPIRE_TIME or "7 days") # pyright: ignore[reportCallIssue]
