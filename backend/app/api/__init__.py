"""API 路由聚合（Phase 2A / 2B / 3C-0）。

各子路由在此汇总，由 main.py 以 prefix="/api" 统一挂载：
  - auth_router       -> /login
  - opinions_router   -> /opinions, /opinions/{id}
  - dashboard_router  -> /dashboard/stats   (Phase 2B)
  - events_router     -> /events, /events/aggregate   (Phase 3C-0)
"""
from fastapi import APIRouter

from app.api.analysis import analysis_router
from app.api.auth import auth_router
from app.api.collector import collector_router
from app.api.dashboard import dashboard_router
from app.api.alerts import alerts_router
from app.api.events import events_router
from app.api.propagation import propagation_router
from app.api.opinions import opinions_router

api_router = APIRouter()
api_router.include_router(auth_router)
# opinions_router 内部路由使用 "" / "/{opinion_id}" 等相对路径，
# 在此统一加 prefix="/opinions"，最终挂载为 /api/opinions、/api/opinions/{id}。
# （若不在本层加前缀，空路径 "" 与无前缀的父路由会触发
#  "Prefix and path cannot be both empty" 错误。）
api_router.include_router(opinions_router, prefix="/opinions")
api_router.include_router(dashboard_router)
# analysis_router 路由本身为 /analyze/{opinion_id}，无需额外前缀，
# 最终挂载为 /api/analyze/{opinion_id}。
api_router.include_router(analysis_router)
# collecter_router 路由本身为 /run、/status，在此统一加 prefix="/collector"，
# 最终挂载为 /api/collector/run、/api/collector/status（Phase 3A）。
api_router.include_router(collector_router, prefix="/collector")
# events_router 路由本身为 /aggregate、""（列表），在此统一加 prefix="/events"，
# 最终挂载为 /api/events/aggregate、/api/events（Phase 3C-0）。
api_router.include_router(alerts_router, prefix="/alerts")
api_router.include_router(events_router, prefix="/events")
api_router.include_router(propagation_router, prefix="/propagation")
