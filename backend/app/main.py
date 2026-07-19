"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from app.api import api_router
from app.core.config import settings

app = FastAPI(
    title="大厂县公安互联网舆情监测研判平台",
    version="0.1.0",
    description="MVP - Phase 2B 认证 + 舆情基础 API + 驾驶舱统计",
)

@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}

app.include_router(api_router, prefix="/api")

_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
