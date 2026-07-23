"""应用配置（Pydantic Settings）。

从 .env 读取（自动查找项目根目录下的 .env），不硬编码敏感信息。
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] = 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(_PROJECT_ROOT / ".env")],
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== 数据库（唯一：PostgreSQL 16；不硬编码，从 .env 读取）=====
    database_url: str = (
        "postgresql+psycopg://opinion_user:opinion_pass@postgres:5432/opinion_db"
    )

    # ===== DeepSeek AI（Phase 2 使用；缺失/失败自动降级）=====
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    # Event-2 Narrative backfill 调用约束（仅影响 DeepSeek 客户端，不改聚合/聚类规则）。
    # 单次请求超时（秒）；超时即视为失败，由上层降级到规则叙事。
    deepseek_timeout: float = 30.0
    # SDK 级重试次数（针对连接/限流/5xx 的指数退避）。
    deepseek_max_retries: int = 2

    # ===== JWT（简单模式：无 OAuth / refresh token / RBAC）=====
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # ===== 初始化管理员 =====
    init_admin_username: str = "admin"
    init_admin_password: str = "admin123"

    # ===== Collector 采集配置（Phase 3B）=====
    # 采集方式（非数据来源）：government | mock
    #   - 生产默认 government（大厂县政府网站）
    #   - 测试默认 mock（conftest 在导入 app 前注入 COLLECTOR_TYPE=mock）
    collector_type: str = "government"
    # P0: scheduled collection
    collector_schedule_enabled: bool = True
    collector_schedule_cron: str = "*/30 * * * *"
    # P0: 预警自动评估（每 N 分钟执行一次，生成新预警记录供前端推送）
    alert_eval_enabled: bool = True
    alert_eval_interval_minutes: int = 30
    # 监测关键词（兜底用）：keywords 表已成为采集过滤 + 预警匹配的唯一权威源
    # （见 app/services/keyword_service.py，表空时回退到此配置）。
    # 历史上为大厂县视角；扩省时仅加「河北」。现由 keywords 表驱动，此值仅作应急兜底。
    collector_keywords: str = "河北,大厂,舆情,消防,安全生产,民生,投诉,廊坊,大厂回族"
    # P0: new data sources
    # 以下开关已在 collectors/service.py:resolve_collectors 中真正生效（此前为死配置）。
    baidu_news_enabled: bool = True
    hebei_news_enabled: bool = True
    hebei_news_feeds: str = ""
    # Phase 2 新增真实数据源开关（均在 resolve_collectors 中真正生效）。
    xinhua_enabled: bool = True
    people_enabled: bool = True
    chinanews_enabled: bool = True
    hebei_daily_enabled: bool = True
    changcheng_enabled: bool = True
    hebei_gov_enabled: bool = True
    # 微博采集：维护成本高、稳定性差，已从运行流程移除（保留 WeiboCollector 类以兼容）。
    # 该开关不再被装配逻辑读取；保留字段仅为向后兼容，建议保持 False。
    weibo_enabled: bool = False
    weibo_cookie: str = ""
    # 政府网站栏目页地址（.env 用逗号分隔字符串亦可，见下方 validator）。
    #   今日大厂 /jrdc.jhtml，公告公示 /gggs.jhtml
    gov_news_urls: List[str] = [
        "https://www.lfdc.gov.cn/jrdc.jhtml",
        "https://www.lfdc.gov.cn/gggs.jhtml",
    ]

    @field_validator("gov_news_urls", mode="before")
    @classmethod
    def _split_gov_news_urls(cls, v: object) -> object:
        """支持 .env 以逗号分隔字符串提供 GOV_NEWS_URLS。"""
        if isinstance(v, str):
            return [u.strip() for u in v.split(",") if u.strip()]
        return v

    # ===== Event 聚合配置（Phase 3C-0）=====
    # 聚合窗口：仅归并最近 N 天内、analysis_status=completed 的 Opinion。
    # Phase 4-Event-1 起：不再要求 keywords 非空（文本相似度也可召回），
    # 但仍以 region + 时间窗口作为候选门槛。
    event_window_days: int = 7

    # ===== Event 聚合配置（Phase 4-Event-1 重构）=====
    # 文本相似度算法：字符 2-gram 余弦（纯 Python，无新依赖，可配置/可测试/可解释）。
    # 高相似度阈值：仅凭文本相似度即可直接判定为同一事件。
    event_text_similarity_threshold: float = 0.45
    # 通用词（内置 16 敏感词）合并阈值：仅共享通用词、且文本相似度达到此值才允许合并，
    # 用于杜绝「火灾」「事故」「投诉」等通用词单独触发伪聚合。
    event_low_merge_text_threshold: float = 0.30
    # 事件延续窗口（天）：已有 Event 允许最近的新 Opinion 延续挂载的时限，
    # 需同时满足时间接近 + 至少一个可靠信号 + 文本相似度阈值；超时不再吸附（杜绝永久吸附）。
    event_continuation_days: int = 14
    # 事件延续所需文本相似度阈值（通常略高于 low_merge，延续要求更可靠）。
    event_continuation_text_threshold: float = 0.35
    # 单条舆情独立成事件的最低风险分：低于此且无非通用高区分度关键词/无 ai_keywords 的
    # 单条 Opinion 不单独建事件（避免空关键词噪声撑爆事件中心），但仍可经延续挂载到既有事件。
    event_singleton_min_risk: int = 40


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
