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
from app.models.event_action import EventAction
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRule, AlertRecord
from app.models.propagation import PropagationNode
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.bocha_search_session import BochaSearchSession
from app.models.bocha_lead import BochaLead
from app.models.bocha_ai_search_session import BochaAISearchSession
from app.models.bocha_ai_lead import BochaAILead
from app.models.role import Role
from app.models.permission import Permission
from app.models.audit import LoginLog, OperationLog
from app.models.report_record import ReportRecord
from app.models.report_template import ReportTemplate
from app.models.foreign_keyword import ForeignKeyword
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_analysis_run import ForeignAnalysisRun
from app.models.foreign_risk_result import ForeignRiskResult
from app.models.foreign_risk_term import ForeignRiskTerm
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_event_run import ForeignEventRun
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_alert_rule import ForeignAlertRule
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_run import ForeignAlertRun
from app.models.foreign_alert_action import ForeignAlertAction
from app.models.foreign_alert_admission import ForeignAlertAdmission
from app.models.foreign_alert_admission_action import ForeignAlertAdmissionAction

__all__ = [
    "Base",
    "User",
    "Region",
    "Opinion",
    "Keyword",
    "Event",
    "EventAction",
    "EventOpinion",
    "AlertRule",
    "AlertRecord",
    "PropagationNode",
    "CollectorRun",
    "DataSource",
    "BochaSearchSession",
    "BochaLead",
    "BochaAISearchSession",
    "BochaAILead",
    "Role",
    "Permission",
    "LoginLog",
    "OperationLog",
    "ReportRecord",
    "ReportTemplate",
    "ForeignKeyword",
    "ForeignOpinion",
    "ForeignAnalysisRun",
    "ForeignRiskResult",
    "ForeignRiskTerm",
    "ForeignAIResult",
    "ForeignEventCandidate",
    "ForeignEvent",
    "ForeignEventOpinion",
    "ForeignEventRun",
    "ForeignEventAction",
    "ForeignAlertRule",
    "ForeignAlert",
    "ForeignAlertRun",
    "ForeignAlertAction",
    "ForeignAlertAdmission",
    "ForeignAlertAdmissionAction",
]
