"""Collector 采集接口（Phase 3A）。

路由（挂载在 /api 下，由 main.py 统一加前缀）：
  POST   /collector/run     触发一次采集 + 自动 AI 分析闭环（Bearer JWT）
  GET    /collector/status  查询采集状态（Bearer JWT，内存，重启丢失）

严格范围（本阶段）：
- 仅「手动触发一次采集」。不做定时 / Celery / Redis / 前端。
- 业务不直接调用 DeepSeek / Provider，统一经 CollectorService -> AIService。
- 采集状态存内存（见 collectors.service._COLLECTOR_STATUS），重启丢失、
  不持久化；代码与 docs 已注明 Phase 3A 临时实现。
- 不修改数据库结构 / 不新增迁移。

采集后自动聚合（新增）：
- 每次采集完成（无论手动 / 定时）都会紧接着跑一次增量聚合，把新入库舆情
  立即聚成事件，无需再单独点「手动聚合」。聚合逻辑与 /events/aggregate 一致，
  且异常安全：聚合失败不影响采集结果（见 app.services.event.aggregator
  .auto_aggregate_after_collect）。
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Request, status
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
from app.services.audit_service import log_operation
from app.services.event.aggregator import auto_aggregate_after_collect

logger = logging.getLogger(__name__)

collector_router = APIRouter(
    tags=["collector"],
    # 全部采集接口均需登录（Bearer JWT）
    dependencies=[Depends(get_current_user)],
)


def _audit_collect_run(session_factory, operator_id, operator_username, task_id, batch_id, result, details):
    """采集结果审计（后台任务内调用，无 request 上下文，ip/ua 为空属正常）。"""
    sdb = session_factory()
    try:
        op = sdb.get(User, operator_id) if operator_id else None
        log_operation(
            sdb, action="COLLECT_RUN", operator=op, request=None,
            resource_type="collection", resource_id=task_id, result=result,
            details={"batch_id": batch_id, "operator": operator_username, **(details or {})},
        )
        sdb.commit()
    except Exception:
        try:
            sdb.rollback()
        except Exception:
            pass
    finally:
        sdb.close()


def _run_collect_task(task, session_factory, operator_id=None, operator_username=None):
    """后台任务体：并发采集 → 自动增量聚合，并实时上报进度。"""
    def _on_progress(done: int, total: int, name: str) -> None:
        task.progress = int(done / total * 100) if total else 100
        task.step = f"已采集 {done}/{total} 个数据源" + (f"（{name}）" if name else "")

    # 关联 task_id ↔ batch_id：采集开始前即生成 batch_id 并写入 Task，
    # 使前端首轮轮询即可拿到 batch_id，从而实时定位本次采集批次。
    batch_id = uuid.uuid4().hex
    task.batch_id = batch_id

    try:
        service = CollectorService()
        result = service.collect_and_analyze_concurrent(
            session_factory, on_progress=_on_progress, batch_id=batch_id
        )
        collect_result = {
            "collector_type": result.collector_type,
            "fetched_raw": result.fetched_raw,
            "created": result.created,
            "analyzed": result.analyzed,
            "failed": result.failed,
        }

        # 采集完成后自动增量聚合：新入库舆情立即聚成事件，无需再手动触发。
        # 与「手动聚合」走同一逻辑；异常安全——聚合失败不废掉采集结果。
        task.step = "采集完成，正在自动聚合事件…"
        collect_result["aggregated"] = auto_aggregate_after_collect(session_factory)
        task.step = "采集与自动聚合完成"
        _audit_collect_run(
            session_factory, operator_id, operator_username, task_id=task.task_id,
            batch_id=batch_id, result="success", details=collect_result,
        )
        return collect_result
    except Exception as exc:
        # 采集整体失败：记录审计（failed），不掩盖异常（任务状态仍由 task_manager 置 failed）。
        _audit_collect_run(
            session_factory, operator_id, operator_username, task_id=task.task_id,
            batch_id=batch_id, result="failed", details={"error": str(exc)[:1000]},
        )
        raise


@collector_router.post(
    "/run",
    response_model=CollectorTaskResponse,
    status_code=status.HTTP_200_OK,
)
def run_collector(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CollectorTaskResponse:
    """触发一次采集 + 自动 AI 分析 + 自动聚合闭环（后台异步执行）。

    本接口立即返回 task_id，采集在后台并发抓取（各数据源独立线程，整体耗时≈最慢
    单源）；采集完成后自动跑一次增量聚合（见 _run_collect_task）。前端通过
    ``GET /api/tasks/{task_id}`` 轮询进度与结果，结果含 ``aggregated`` 字段。

    Phase 3B：政府网站采集 5 秒内重复触发 → 429（任务会直接失败，错误信息提示频繁）。

    Phase 6 P1-4：记录手动触发审计（action=COLLECT）。
    """
    task_id = start_task("collector", _run_collect_task, SessionLocal, current_user.id, current_user.username)
    # 触发审计（任务已接受即记为 success；真实采集结果由后台任务内 COLLECT_RUN 记录）
    log_operation(
        db, action="COLLECT", operator=current_user, request=request,
        resource_type="collection", resource_id=task_id, result="success",
        details={"trigger_type": "manual"},
    )
    db.commit()
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
