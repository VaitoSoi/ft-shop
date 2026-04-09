from contextlib import asynccontextmanager

from fastapi import FastAPI

from lib.db import init
from routes import subscription_router, user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init()
    yield


app = FastAPI(
    title="Flavortownn Store PubSub API",
    lifespan=lifespan,
    license_info={"name": "MIT", "url": "https://opensource.org/license/mit"},
)
app.include_router(subscription_router)
app.include_router(user_router)
