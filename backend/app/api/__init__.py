"""API 璺敱鑱氬悎锛圥hase 2A / 2B / 3C-0锛夈€?

鍚勫瓙璺敱鍦ㄦ姹囨€伙紝鐢?main.py 浠?prefix="/api" 缁熶竴鎸傝浇锛?
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
from app.api.keywords import keywords_router
from app.api.sources import sources_router
from app.api.users import users_router
from app.api.opinions import opinions_router
from app.api.reports import reports_router
from app.api.admin_data_sources import admin_ds_router
from app.api.tasks import tasks_router

api_router = APIRouter()
api_router.include_router(auth_router)
# opinions_router 鍐呴儴璺敱浣跨敤 "" / "/{opinion_id}" 绛夌浉瀵硅矾寰勶紝
# 鍦ㄦ缁熶竴鍔?prefix="/opinions"锛屾渶缁堟寕杞戒负 /api/opinions銆?api/opinions/{id}銆?
# 锛堣嫢涓嶅湪鏈眰鍔犲墠缂€锛岀┖璺緞 "" 涓庢棤鍓嶇紑鐨勭埗璺敱浼氳Е鍙?
#  "Prefix and path cannot be both empty" 閿欒銆傦級
api_router.include_router(opinions_router, prefix="/opinions")
api_router.include_router(dashboard_router)
# analysis_router 璺敱鏈韩涓?/analyze/{opinion_id}锛屾棤闇€棰濆鍓嶇紑锛?
# 鏈€缁堟寕杞戒负 /api/analyze/{opinion_id}銆?
api_router.include_router(analysis_router)
# collecter_router 璺敱鏈韩涓?/run銆?status锛屽湪姝ょ粺涓€鍔?prefix="/collector"锛?
# 鏈€缁堟寕杞戒负 /api/collector/run銆?api/collector/status锛圥hase 3A锛夈€?
api_router.include_router(collector_router, prefix="/collector")
# events_router 璺敱鏈韩涓?/aggregate銆?"锛堝垪琛級锛屽湪姝ょ粺涓€鍔?prefix="/events"锛?
# 鏈€缁堟寕杞戒负 /api/events/aggregate銆?api/events锛圥hase 3C-0锛夈€?
api_router.include_router(alerts_router, prefix="/alerts")
api_router.include_router(events_router, prefix="/events")
api_router.include_router(propagation_router, prefix="/propagation")
api_router.include_router(keywords_router, prefix="/keywords")
api_router.include_router(users_router)
api_router.include_router(sources_router)
api_router.include_router(reports_router)
# 数据源管理后台（router 内部已带 prefix="/admin/data-sources"）
api_router.include_router(admin_ds_router)
# 后台任务状态查询（GET /api/tasks/{task_id}）
api_router.include_router(tasks_router, prefix="/tasks")

