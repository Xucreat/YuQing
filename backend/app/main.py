"""FastAPI 应用入口。"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api import api_router
from app.core.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    # Phase 6 P1-1：启动时对历史「仍 running」的 CollectorRun 做超时对账回收，
    # 仅回收超过 collector_run_zombie_timeout_minutes 的记录，避免误判在途任务。
    try:
        from app.collectors.service import reclaim_zombie_runs

        db = SessionLocal()
        try:
            n = reclaim_zombie_runs(db)
            if n:
                logger.info("启动对账：回收 %d 条超时僵尸采集运行记录", n)
        finally:
            db.close()
    except SQLAlchemyError:
        logger.exception("启动僵尸采集记录回收失败（不影响应用启动）")
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="公安互联网舆情监测研判平台",
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
    # 暴露数据源发现是否降级（DB 异常回退 DEFAULT_SOURCES 必须可观测，禁止静默）。
    from app.collectors import registry as _registry
    degraded = _registry.last_discovery_degraded
    return {
        "status": "ok",
        "collector_discovery": "degraded" if degraded else "db_driven",
        "collector_discovery_error": _registry.last_discovery_error if degraded else None,
    }

app.include_router(api_router, prefix="/api")

_static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))

# SPA 缓存策略（修复：前端发版后浏览器仍加载旧 index.html 导致新功能"消失"）
# 背景：index.html 此前由 FileResponse 直出且不带任何 Cache-Control，浏览器会按
# RFC 9111 的启发式规则(约 last-modified 距今时长的 10%)自行缓存；又因部署脚本
# 只增量复制、不清理历史 chunk，旧 index.html 引用的旧 assets 仍可 200 命中，
# 于是页面表现"正常"但功能停留在旧版本。
# 规则：带内容 hash 的 /assets/* 可长期强缓存；index.html 等入口文件必须每次回源校验。
_ENTRY_NO_CACHE = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}
_HASHED_ASSET_CACHE = {"Cache-Control": "public, max-age=31536000, immutable"}

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
            # vite 产物文件名自带 content hash，内容变更必然换名，可安全长缓存
            if path.startswith("assets/"):
                return FileResponse(fp, headers=_HASHED_ASSET_CACHE)
            return FileResponse(fp, headers=_ENTRY_NO_CACHE)
        # 缺失的资源请求（带扩展名的静态文件，如 .js/.css/.json/.png）必须返回 404，
        # 绝不能 fallback 到 index.html——否则浏览器会把 HTML 当 JS 解析导致模块崩溃
        # （典型症状：清理旧 chunk 后，缓存旧 index.html 的浏览器加载驾驶舱等页面报渲染错误）。
        # 仅对无扩展名的路由（SPA 前端路由如 /command-screen）做 index.html 回退。
        last_segment = path.rsplit("/", 1)[-1]
        if "." in last_segment:
            from fastapi.responses import Response

            return Response(status_code=404, headers=_ENTRY_NO_CACHE)
        # Fallback: serve index.html for SPA client-side routes (no file extension)
        index = os.path.join(_static_dir, "index.html")
        if os.path.isfile(index):
            return FileResponse(index, headers=_ENTRY_NO_CACHE)
        return await call_next(request)
