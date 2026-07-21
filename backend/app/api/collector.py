"""Collector 采集接口（Phase 3A）。

路由（挂载在 /api 下，由 main.py 统一加前缀）：
  POST   /collector/run     触发一次采集 + 自动 AI 分析闭环（Bearer JWT）
  GET    /collector/status  查询采集状态（Bearer JWT，内存，重启丢失）

严格范围（本阶段）：
- 仅「手动触发一次采集」。不做定时 / Celery / Redis / 事件聚合 / 前端。
- 业务不直接调用 DeepSeek / Provider，统一经 CollectorService -> AIService。
- 采集状态存内存（见 collectors.service._COLLECTOR_STATUS），重启丢失、
  不持久化；代码与 docs 已注明 Phase 3A 临时实现。
- 不修改数据库结构 / 不新增迁移。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.collectors.service import (
    CollectorService,
    CollectorThrottled,
    get_collector_status,
)
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.collector import CollectorRunResponse, CollectorStatusResponse

collector_router = APIRouter(
    tags=["collector"],
    # 全部采集接口均需登录（Bearer JWT）
    dependencies=[Depends(get_current_user)],
)


@collector_router.post(
    "/run",
    response_model=CollectorRunResponse,
    status_code=status.HTTP_200_OK,
)
def run_collector(
    response: Response,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> CollectorRunResponse:
    """触发一次采集 + 自动 AI 分析闭环。

    流程：按 settings.collector_type 选择 Collector（government / mock）
          -> Collector.fetch() -> 按 url 去重 -> 建 Opinion(pending)
          -> AIService.analyze -> 写回字段 + 状态流转(completed/failed)。
    返回：collector_type（采集方式）/ created / analyzed / failed。

    Phase 3B：政府网站采集 5 秒内重复触发 → 返回 429（success=false），
    避免误操作连续请求政府网站（不使用 500）。
    """
    service = CollectorService()
    try:
        result = service.collect_and_analyze(db)
    except CollectorThrottled:
        # 5 秒防抖：过于频繁 → 429 Too Many Requests（不判为服务错误）。
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return CollectorRunResponse(
            success=False,
            collector_type=service.collector_type,
            message="collector running too frequently",
        )
    return CollectorRunResponse(
        success=True,
        collector_type=result.collector_type,
        fetched_raw=result.fetched_raw,
        created=result.created,
        analyzed=result.analyzed,
        failed=result.failed,
        message="采集完成",
    )


@collector_router.get(
    "/status",
    response_model=CollectorStatusResponse,
    status_code=status.HTTP_200_OK,
)
def collector_status(
    _current_user: User = Depends(get_current_user),
) -> CollectorStatusResponse:
    """查询采集状态（模块级内存，重启丢失；Phase 3A 临时实现）。"""
    st = get_collector_status()
    return CollectorStatusResponse(
        last_run=st.get("last_run"),
        total_collected=st.get("total_collected", 0),
        collector_type=st.get("collector_type"),
    )
