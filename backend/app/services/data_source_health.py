"""Derived health summaries for a DataSource.

This service intentionally reads DataSource and CollectorRun only.  Nothing is
persisted, and the historical error message is never replaced.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.services.error_codes import normalize_error_code


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class DataSourceHealthSummaryService:
    """Calculate a source health snapshot from the most recent runs."""

    def __init__(self, *, stale_after_days: int = 7, fresh_within_hours: int = 48) -> None:
        self.stale_after_days = stale_after_days
        self.fresh_within_hours = fresh_within_hours

    @staticmethod
    def _is_failure(run: CollectorRun) -> bool:
        return run.status in {"failed", "error"} or int(getattr(run, "failed", 0) or 0) > 0

    @staticmethod
    def _is_success(run: CollectorRun) -> bool:
        return run.status == "success" and not int(getattr(run, "failed", 0) or 0)

    def summarize(
        self,
        datasource: DataSource,
        runs: Iterable[CollectorRun],
        *,
        now: datetime | None = None,
    ) -> dict:
        now_utc = _as_utc(now) or datetime.now(timezone.utc)
        ordered = sorted(
            list(runs),
            key=lambda run: (_as_utc(getattr(run, "start_time", None)) or datetime.min.replace(tzinfo=timezone.utc), getattr(run, "id", 0) or 0),
            reverse=True,
        )
        base = {
            "datasource_id": datasource.id,
            "health_status": "paused" if not datasource.enabled else "unknown",
            "last_run_at": None,
            "last_success_at": None,
            "last_failure_at": None,
            "consecutive_failures": 0,
            "last_error_code": None,
            "last_error_message": None,
            "last_valid_data_time": None,
            "data_freshness": "unknown",
            "health_reason": "数据源已停用" if not datasource.enabled else "从未运行",
        }
        if not datasource.enabled or not ordered:
            return base

        latest = ordered[0]
        latest_at = _as_utc(getattr(latest, "start_time", None))
        base["last_run_at"] = latest_at.isoformat() if latest_at else None
        failures = [run for run in ordered if self._is_failure(run)]
        base["consecutive_failures"] = next(
            (index for index, run in enumerate(ordered) if not self._is_failure(run)),
            len(ordered),
        )
        success_runs = [run for run in ordered if self._is_success(run)]
        failure_runs = [run for run in ordered if self._is_failure(run)]
        last_success = _as_utc(getattr(success_runs[0], "start_time", None)) if success_runs else None
        last_failure = _as_utc(getattr(failure_runs[0], "start_time", None)) if failure_runs else None
        base["last_success_at"] = last_success.isoformat() if last_success else None
        base["last_failure_at"] = last_failure.isoformat() if last_failure else None

        latest_failure = failure_runs[0] if failure_runs else None
        if latest_failure is not None:
            base["last_error_message"] = getattr(latest_failure, "error_msg", None)
            base["last_error_code"] = normalize_error_code(base["last_error_message"])

        valid_runs = [
            run for run in ordered
            if self._is_success(run)
            and (int(getattr(run, "fetched_raw", 0) or 0) > 0 or int(getattr(run, "created", 0) or 0) > 0)
        ]
        last_valid = _as_utc(getattr(valid_runs[0], "start_time", None)) if valid_runs else None
        base["last_valid_data_time"] = last_valid.isoformat() if last_valid else None
        if last_valid is not None:
            age = now_utc - last_valid
            base["data_freshness"] = "fresh" if age <= timedelta(hours=self.fresh_within_hours) else "stale"

        if base["consecutive_failures"] > 0 and base["last_error_code"] in {"TOKEN_EXPIRED", "AUTH_FAILED"}:
            base["health_status"] = "unhealthy"
            base["health_reason"] = base["last_error_code"]
        elif base["consecutive_failures"] >= 3:
            base["health_status"] = "unhealthy"
            base["health_reason"] = f"连续失败 {base['consecutive_failures']} 次"
        elif 1 <= base["consecutive_failures"] <= 2:
            base["health_status"] = "degraded"
            base["health_reason"] = f"连续失败 {base['consecutive_failures']} 次"
        elif last_valid is None:
            base["health_status"] = "degraded" if latest_at and now_utc - latest_at > timedelta(days=self.stale_after_days) else "healthy"
            base["health_reason"] = "最近运行成功但暂无有效数据" if base["health_status"] == "healthy" else "长期无有效数据"
        elif base["data_freshness"] == "stale":
            base["health_status"] = "degraded"
            base["health_reason"] = "成功但长期无有效数据"
        else:
            base["health_status"] = "healthy"
            base["health_reason"] = "最近运行成功，数据正常"
        return base

    # Compatibility spelling for service consumers.
    calculate = summarize
    get_summary = summarize
