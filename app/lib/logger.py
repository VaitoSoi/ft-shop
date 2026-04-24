from datetime import datetime
from logging import FileHandler, getLogger

from .env import LOGGING_FILE, LOGGING_LEVEL

logger = getLogger("uvicorn")
logger.setLevel(LOGGING_LEVEL)

if LOGGING_FILE in ["default", "date"]:
    if LOGGING_FILE == "default":
        file = FileHandler("./logs/.log", "a+")
    elif LOGGING_FILE == "date":
        now = datetime.now()
        file = FileHandler(f"./logs/{now.strftime("%d-%m-%y %X")}.log", "a+")
    else:
        raise
    logger.addHandler(file)