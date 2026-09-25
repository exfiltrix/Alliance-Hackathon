from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.config import settings
from app.db import init_engine
from app.automation import warmup, watcher
from app.routers import check, crash_test, devices, inbox, passport, seal, stats, verify


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()
    with db.SessionLocal() as session:
        crash_test.seed_models(session)
    if settings.warmup:
        warmup.start()
    if settings.watch_enabled:
        watcher.start()
    yield
    watcher.stop()


app = FastAPI(title="MedSeal API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex or None,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

for r in (devices.router, seal.router, verify.router, inbox.router, check.router, crash_test.router, passport.router,
          stats.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
