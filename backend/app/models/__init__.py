"""ORM 模型聚合导入。

导入本模块即可把全部模型注册到 Base.metadata，
供 Alembic 迁移与脚本使用。
"""
from app.db.base import Base
from app.models.user import User
from app.models.region import Region
from app.models.opinion import Opinion
from app.models.keyword import Keyword
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRule, AlertRecord
from app.models.propagation import PropagationNode
from app.models.collector_run import CollectorRun
from app.models.role import Role
from app.models.role import Role

__all__ = [
    "Base",
    "User",
    "Region",
    "Opinion",
    "Keyword",
    "Event",
    "EventOpinion",
    "AlertRule",
    "AlertRecord",
    "PropagationNode",
    "CollectorRun",
    "Role",
    "Role",
]
