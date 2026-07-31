"""舆情报告响应模型（P2 报告自动生成 + PDF 导出 / Phase Report-1 可配置生成器）。"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from app.schemas.dashboard import (
    KeywordItem,
    RegionItem,
    SentimentItem,
    SourceItem,
    TrendItem,
)


class ReportOpinionItem(BaseModel):
    """高风险舆情 TOP 条目。"""

    id: int
    title: str
    source: str
    region_name: str
    risk_score: int
    sentiment: str
    created_at: str
    summary: str


class ReportEventItem(BaseModel):
    """重点事件条目。"""

    id: int
    title: str
    risk_level: str
    opinion_count: int


class ReportOverviewResponse(BaseModel):
    """舆情报告总览（JSON，供前端预览 / PDF 渲染共用）。"""

    generated_at: str
    period_days: int
    total: int
    today: int
    high_risk: int
    event_count: int
    risk_rate: float
    negative_rate: float
    trend: List[TrendItem]
    top_keywords: List[KeywordItem]
    top_sources: List[SourceItem]
    top_regions: List[RegionItem]
    top_risky: List[ReportOpinionItem]
    events: List[ReportEventItem]
    sentiments: List[SentimentItem]


# ---------------------------------------------------------------------------
# Phase Report-1：可配置报告生成器
# ---------------------------------------------------------------------------
class ReportModuleParamDef(BaseModel):
    """模块可配置参数的元信息（供前端渲染表单）。"""

    key: str
    label: str
    type: str = "int"
    default: Any = None
    min: Optional[int] = None
    max: Optional[int] = None


class ReportModuleDef(BaseModel):
    """单个可选报告模块的元信息。

    Phase Report-2-P1 新增 name / default_enabled / params；title 保留不变，
    Phase Report-1.1 前端（读 key/title/description）零破坏。
    """

    key: str
    name: str
    title: str
    description: str
    default_enabled: bool = True
    params: List[ReportModuleParamDef] = Field(default_factory=list)


class ReportModulesResponse(BaseModel):
    """GET /reports/modules 返回：所有可选模块 + 默认选中的模块。"""

    modules: List[ReportModuleDef]
    default_modules: List[str]


class ReportGenerateRequest(BaseModel):
    """POST /reports/generate 请求体（Legacy，Phase Report-1.1 已上线）。"""

    report_name: str = "舆情监测报告"
    time_field: Literal["created_at", "publish_time"] = "created_at"
    start_date: Optional[str] = None  # "YYYY-MM-DD"
    end_date: Optional[str] = None
    days: int = 7
    module_keys: List[str]


# ---------------------------------------------------------------------------
# Phase Report-2-P1：正式导出入口 POST /reports/export
# ---------------------------------------------------------------------------
class ReportModuleSelection(BaseModel):
    """带参数的模块选择项（modules 支持 "key" 字符串或本对象两种写法）。"""

    key: str
    params: Dict[str, Any] = Field(default_factory=dict)


class ReportExportRequest(BaseModel):
    """POST /reports/export 请求体。

    时间口径为本地（Asia/Shanghai）日期语义，不做任何时区转换
    （Phase Report-2-P0 决策：方案 A）。
    """

    name: str = "舆情监测报告"
    time_field: Literal["created_at", "publish_time"] = "created_at"
    range_type: Literal["last_n_days", "custom"] = "last_n_days"
    range_days: int = Field(default=7, ge=1, le=365)
    start_date: Optional[str] = None  # "YYYY-MM-DD"（range_type=custom 必填）
    end_date: Optional[str] = None
    modules: List[Union[str, ReportModuleSelection]] = Field(default_factory=list)
    # 当前阶段仅支持 download；email 留作 Phase 5 邮件能力，此处显式拒绝。
    delivery: Literal["download", "email"] = "download"
    recipients: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase Report-4-A：报告模板（最小可用：保存/加载）
# ---------------------------------------------------------------------------
class ReportTemplateConfig(BaseModel):
    """模板保存的「导出配置快照」结构。

    与 ReportExportRequest 同构，但剔除 delivery / recipients
    （模板只描述「怎么生成」，不描述「怎么投递」）。
    """

    name: str = "舆情监测报告"
    time_field: Literal["created_at", "publish_time"] = "created_at"
    range_type: Literal["last_n_days", "custom"] = "last_n_days"
    range_days: int = Field(default=7, ge=1, le=365)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    modules: List[Union[str, ReportModuleSelection]] = Field(default_factory=list)


class ReportTemplateCreate(BaseModel):
    """POST /reports/templates 请求体。"""

    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=255)
    is_public: bool = False
    config_json: ReportTemplateConfig


class ReportTemplateUpdate(BaseModel):
    """PUT /reports/templates/{id} 请求体（全字段可选）。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=255)
    is_public: Optional[bool] = None
    config_json: Optional[ReportTemplateConfig] = None


class ReportTemplateResponse(BaseModel):
    """模板对外返回（含 can_edit 标记，供前端决定是否展示删除/编辑）。"""

    id: int
    name: str
    description: Optional[str] = None
    owner_id: int
    config_json: ReportTemplateConfig
    is_public: bool
    created_at: str
    updated_at: str
    can_edit: bool
