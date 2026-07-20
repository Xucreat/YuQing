"""FastAPI 应用入口。"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
from contextlib import asynccontextmanager

from app.api import api_router
from app.core.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="大厂县公安互联网舆情监测研判平台",
    version="0.1.0",
    lifespan=lifespan,
    description="MVP - Phase 2B 认证 + 舆情基础 API + 驾驶舱统计",
)

# 允许任意来源跨域访问（CORS 全开）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/_debug_static", tags=["debug"])
def debug_static():
    import json
    idx = os.path.join(_static_dir, "index.html")
    return {"static_dir": _static_dir, "index_exists": os.path.isfile(idx), "index_size": os.path.getsize(idx) if os.path.isfile(idx) else 0}

@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}

app.include_router(api_router, prefix="/api")

_static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))

if os.path.isdir(_static_dir):
    # Middleware: if a static file exists, serve it. Otherwise serve index.html (SPA fallback).
    @app.middleware("http")
    async def spa_middleware(request: Request, call_next):
        # Let API routes and health check pass through
        if request.url.path.startswith("/api") or request.url.path.startswith("/health"):
            return await call_next(request)
        # Try to serve as static file
        path = request.url.path.lstrip("/")
        fp = os.path.join(_static_dir, path)
        if path and os.path.isfile(fp):
            return FileResponse(fp)
        # Fallback: serve index.html for any other path (SPA routing)
        index = os.path.join(_static_dir, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)
        return await call_next(request)
