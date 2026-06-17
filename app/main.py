from fastapi import FastAPI
from app.routes import health, offer, web, demo

app = FastAPI(
    title="OfferIQ",
    description="Job Offer Intelligence Platform — evaluate, compare, and negotiate offers",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(offer.router)
app.include_router(demo.router)
app.include_router(web.router)


@app.get("/ping")
async def ping():
    return {"ping": "pong"}
