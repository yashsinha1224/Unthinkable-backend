from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import threading
from sse.connection_manager import bind_loop
import asyncio
from routes import (
    complaint,
    notice,
    dashboard,
    user,
    events,
)
from auth import google_oauth, password_handler
from celery_app import celery_app

app = FastAPI(title="Society Maintenance Tracker API", version="0.1.0")

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _start_celery_worker():
    celery_app.worker_main(argv=["worker", "--loglevel=info", "--pool=solo", "--concurrency=1"])


@app.on_event("startup")
async def _bind_realtime_loop():
    bind_loop(asyncio.get_running_loop())
    threading.Thread(target=_start_celery_worker, daemon=True).start()


app.include_router(password_handler.router)
app.include_router(google_oauth.router)
app.include_router(complaint.router)
app.include_router(notice.router)
app.include_router(dashboard.router)
app.include_router(user.router)
app.include_router(events.router)


@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok"}