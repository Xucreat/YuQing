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

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.collectors.service import (
    CollectorService,
    CollectorThrottled,
    get_collector_status,
)
from app.core.dependencies import get_current_user
from app.core.task_manager import start_task
from app.db.session import SessionLocal, get_db
from app.models.user import User
from app.schemas.collector import (
    CollectorStatusResponse,
    CollectorTaskResponse,
)

collector_router = APIRouter(
    tags=["collector"],
    # 全部采集接口均需登录（Bearer JWT）
    dependencies=[Depends(get_current_user)],
)


def _run_collect_task(task, session_factory):
    """后台任务体：并发采集，并实时上报进度。"""
    def _on_progress(done: int, total: int, name: str) -> None:
        task.progress = int(done / total * 100) if total else 100
        task.step = f"已采集 {done}/{total} 个数据源" + (f"（{name}）" if name else "")

    service = CollectorService()
    result = service.collect_and_analyze_concurrent(
        session_factory, on_progress=_on_progress
    )
    return {
        "collector_type": result.collector_type,
        "fetched_raw": result.fetched_raw,
        "created": result.created,
        "analyzed": result.analyzed,
        "failed": result.failed,
    }


@collector_router.post(
    "/run",
    response_model=CollectorTaskResponse,
    status_code=status.HTTP_200_OK,
)
def run_collector(
    _current_user: User = Depends(get_current_user),
) -> CollectorTaskResponse:
    """触发一次采集 + 自动 AI 分析闭环（后台异步执行）。

    本接口立即返回 task_id，采集在后台并发抓取（各数据源独立线程，整体耗时≈最慢
    单源）。前端通过 ``GET /api/tasks/{task_id}`` 轮询进度与结果。

    Phase 3B：政府网站采集 5 秒内重复触发 → 429（任务会直接失败，错误信息提示频繁）。
    """
    task_id = start_task("collector", _run_collect_task, SessionLocal)
    return CollectorTaskResponse(success=True, task_id=task_id, message="采集中")


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
