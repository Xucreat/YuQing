"""进程内后台任务管理器（轻量，无 Celery / Redis）。

用于把「采集数据」「手动聚合」等长耗时同步操作改为后台任务：
- 接口层立即返回 task_id，前端轮询 GET /api/tasks/{task_id} 获取进度与结果；
- 任务在独立线程池中执行，不阻塞 HTTP 请求线程；
- 任务状态存内存（重启丢失），与现有 CollectorService 内存状态一致。

设计约束（与项目既有约定一致）：
- 不引入 Celery / Redis / MQ / 新表 / 新迁移；
- DB 会话不允许跨线程共享：worker 内部用 SessionLocal() 自行创建会话。
"""
from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

# 后台任务线程池（与请求处理线程池隔离）。
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="bg-task")

_tasks: dict[str, "Task"] = {}
_tasks_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Task:
    """单个后台任务的状态容器（属性由 worker 线程更新）。"""

    def __init__(self, task_id: str, task_type: str) -> None:
        self.task_id = task_id
        self.task_type = task_type
        self.batch_id: Optional[str] = None
        self.status = STATUS_PENDING
        self.progress: int = 0          # 0-100
        self.step: str = ""             # 人类可读当前步骤
        self.message: str = ""
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.created_at: Optional[datetime] = _now()
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "batch_id": self.batch_id,
            "status": self.status,
            "progress": self.progress,
            "step": self.step,
            "message": self.message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


def start_task(task_type: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    """启动一个后台任务。

    func 签名为 ``func(task: Task, *args, **kwargs)``；worker 会在调用前注入
    当前 Task 对象，便于 func 通过 ``task.progress`` / ``task.step`` 上报进度。

    返回 task_id；任务在独立线程执行，接口层可立即返回。
    """
    task_id = uuid.uuid4().hex
    task = Task(task_id, task_type)
    with _tasks_lock:
        _tasks[task_id] = task

    def _runner() -> None:
        task.status = STATUS_RUNNING
        task.started_at = _now()
        try:
            result = func(task, *args, **kwargs)
            task.result = result
            task.status = STATUS_SUCCESS
            task.progress = 100
            if not task.message:
                task.message = "完成"
        except Exception as exc:  # 任务失败不应让工作线程崩溃
            logger.exception("后台任务 %s 执行失败", task_id)
            task.error = str(exc) or exc.__class__.__name__
            task.status = STATUS_FAILED
            if not task.message:
                task.message = f"失败: {task.error}"
        finally:
            task.finished_at = _now()

    _executor.submit(_runner)
    return task_id


def get_task(task_id: str) -> Optional[Task]:
    with _tasks_lock:
        return _tasks.get(task_id)
