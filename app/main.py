from contextlib import asynccontextmanager

from apscheduler.schedulers.base import STATE_STOPPED
from fastapi import FastAPI

from app.lib.cron import scheduler
from app.lib.db import init
from app.lib.env import ENV
from app.routes import subscription_router, user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if ENV != "test":
        await init()
        scheduler.start()
    
    yield

    if scheduler.state != STATE_STOPPED:
        scheduler.shutdown()


app = FastAPI(
    title="Flavortown Store Webhook API",
    lifespan=lifespan,
    license_info={"name": "MIT", "url": "https://opensource.org/license/mit"},
)
app.include_router(subscription_router)
app.include_router(user_router)
