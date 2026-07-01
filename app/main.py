import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from app.routes import health, offer, web, demo

SHUTDOWN_DRAIN_TIMEOUT = 30.0
_in_flight_requests = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    deadline = asyncio.get_event_loop().time() + SHUTDOWN_DRAIN_TIMEOUT
    while _in_flight_requests > 0 and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)


app = FastAPI(
    title="OfferIQ",
    description="Job Offer Intelligence Platform — evaluate, compare, and negotiate offers",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def track_in_flight_requests(request: Request, call_next):
    global _in_flight_requests
    _in_flight_requests += 1
    try:
        return await call_next(request)
    finally:
        _in_flight_requests -= 1


app.include_router(health.router)
app.include_router(offer.router)
app.include_router(demo.router)
app.include_router(web.router)


@app.get("/ping")
async def ping():
    return {"ping": "pong"}
