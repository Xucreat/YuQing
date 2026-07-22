"""后台任务状态查询接口。

  GET /api/tasks/{task_id}  查询任务进度/结果（Bearer JWT）

任务由 task_manager 管理（内存态，重启丢失），前端轮询此接口获取进度。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.task_manager import get_task
from app.db.session import get_db
from app.models.user import User

tasks_router = APIRouter(
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)


@tasks_router.get("/{task_id}")
def task_status(
    task_id: str,
    _current_user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
) -> dict:
    """查询后台任务状态（pending/running/success/failed + 进度与结果）。"""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或已过期"
        )
    return task.to_dict()
