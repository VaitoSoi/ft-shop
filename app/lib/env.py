import os

import python_ms as ms
from dotenv import load_dotenv


def is_trueish(val) -> bool:
    return val in ["true", "1", "yes"]


OVERRIDE = os.getenv("OVERIDE", "false") in ["true", "1", "yes"]

ENV = os.getenv("ENV", "dev").lower()
if ENV == "test":
    os.environ["DB_URL"] = "sqlite+aiosqlite://"
    os.environ["TOKEN"] = "empty_token"
    os.environ["NOTIFY_WHEN_EMPTY"] = "true"

elif ENV == "dev":
    load_dotenv(override=OVERRIDE)


def require_env(var: str):
    val = os.getenv(var)
    if val is None:
        raise RuntimeError(f"env {var} is required")
    return val


DB_URL = require_env("DB_URL")
TOKEN = require_env("TOKEN")
BASE_URL = os.getenv("BASE_URL", "https://flavortown.hackclub.com/api/v1/")
NOTIFY_WHEN_EMPTY = is_trueish(os.getenv("NOTIFY_WHEN_EMPTY", "true").lower())
INTERVAL = int(os.getenv("INTERVAL", "30"))
TIMEOUT = int(os.getenv("TIMEOUT", "10"))
MAX_INSTANCES = int(os.getenv("MAX_INSTANCES", "1"))
LOGGING_FILE = os.getenv("LOGGING_FILE", "default") # 'default' use file, 'date' use date as file name, <other> dont use
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "DEBUG").upper()
EXPIRE_TIME = ms(os.getenv("EXPIRE_TIME", "7 days")) # type: ignore