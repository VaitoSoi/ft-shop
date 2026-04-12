from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.lib.cron import scheduler
from app.lib.db import init
from app.routes import subscription_router, user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Flavortownn Store Webhook API",
    lifespan=lifespan,
    license_info={"name": "MIT", "url": "https://opensource.org/license/mit"},
)
app.include_router(subscription_router)
app.include_router(user_router)
