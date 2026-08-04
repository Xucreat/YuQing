"""数据源只读查询仓储（Phase DataSource-Schedule-Fix-2）。

将 scheduler 与 registry 各自内联的 ``data_sources`` 查询统一收敛到此处，
避免两处维护重复的 SQL 条件（SELECT * / 过滤字段漂移风险，Audit-2 R1）。

设计约束：
- 轻量封装，不引入 ORM Repository 框架；
- 所有方法接收调用方已持有的 db 会话（与现有 registry / scheduler 一致）；
- 仅选取所需字段（禁止 SELECT *）；
- 只读：不提供写方法。claim 推进 next_collect_time 仍由 scheduler 负责，
  以保留单事务原子性的既有语义。

返回结构统一为 dict 列表，字段见各函数 docstring。
"""
from __future__ import annotations

from typing import List

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.data_source import DataSource

# scheduler / registry 共用的排除项：八爪鱼微博消费由独立 job 负责。
EXCLUDED_KEYS = ("weibo_octopus",)


def enabled_sources(db: Session) -> List[dict]:
    """装配所需字段：所有 enabled 数据源（按 priority, id 排序）。

    供 registry 做表驱动装配。返回行结构：
    ``{id, key, name, class_path, scope_region_codes, config_json}``

    DB 异常由调用方（registry._resolve_core）捕获并置降级标记，
    此处只负责查询，不吞异常。
    """
    rows = (
        db.execute(
            select(
                DataSource.id,
                DataSource.key,
                DataSource.name,
                DataSource.class_path,
                DataSource.scope_region_codes,
                DataSource.config_json,
            )
            .where(DataSource.enabled == True)  # noqa: E712
            .order_by(DataSource.priority.asc(), DataSource.id.asc())
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def due_scheduled_sources(db: Session) -> List[dict]:
    """逐源 tick 模式：已到采集时间的启用源。

    条件：``enabled AND schedule_enabled AND key != 'weibo_octopus'
          AND (next_collect_time IS NULL OR next_collect_time <= now())``

    返回行结构：
    ``{id, key, schedule_enabled, schedule_interval_minutes, next_collect_time}``

    调用方（scheduler._run_collector_tick）拿到 id 集合后自行 claim 推进
    next_collect_time（写操作不在此处）。
    """
    rows = (
        db.execute(
            text(
                """
                SELECT id, key, schedule_enabled, schedule_interval_minutes, next_collect_time
                FROM data_sources
                WHERE enabled = true
                  AND schedule_enabled = true
                  AND key != 'weibo_octopus'
                  AND (next_collect_time IS NULL OR next_collect_time <= now())
                """
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def scheduled_enabled_sources(db: Session) -> List[dict]:
    """cron 模式候选集：启用且开启自动采集的源（不考虑 next_collect_time）。

    cron 模式由全局 cron 表达式驱动采集节奏，next_collect_time 不参与选择，
    但仍须遵守 schedule_enabled 语义，与逐源 tick 保持一致（Fix-2）。

    条件：``enabled AND schedule_enabled AND key != 'weibo_octopus'``

    返回行结构：``{id, key}``
    """
    rows = (
        db.execute(
            text(
                """
                SELECT id, key
                FROM data_sources
                WHERE enabled = true
                  AND schedule_enabled = true
                  AND key != 'weibo_octopus'
                """
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]
