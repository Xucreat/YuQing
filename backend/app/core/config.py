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
    # ARCH-10 同源残留清理：原公开弱默认值 "admin123" 已移除。
    # 该字段仅在 init_db 首次创建 admin 时使用；为空/未配置时由下方
    # validator 给出明确启动提示，要求通过 .env 的 INIT_ADMIN_PASSWORD
    # 显式设置强密码，杜绝弱口令兜底。已存在 admin 时不会被写入。
    init_admin_password: str = ""

    # ===== Collector 采集配置（Phase 3B）=====
    # 采集方式（非数据来源）：government | mock
    #   - 生产默认 government（大厂县政府网站）
    #   - 测试默认 mock（conftest 在导入 app 前注入 COLLECTOR_TYPE=mock）
    collector_type: str = "government"
    # P0: scheduled collection
    collector_schedule_enabled: bool = True
    collector_schedule_cron: str = "*/30 * * * *"
    # 八爪鱼任务按小时生产，消费端在每小时 15 分执行，避开任务完成窗口。
    weibo_consumer_schedule_cron: str = "15 * * * *"
    # P0: 预警自动评估（每 N 分钟执行一次，生成新预警记录供前端推送）
    alert_eval_enabled: bool = True
    alert_eval_interval_minutes: int = 30
    # ===== Phase DataSource-Schedule-1：按源自定义采集频率 =====
    # 调度模式：per_source（按 next_collect_time 逐源 tick 派发）/ cron（回滚为全局固定 cron）
    collector_schedule_mode: str = "per_source"
    # 全局默认采集间隔（分钟），作为 summary 兜底与新建源缺省
    collector_default_interval_minutes: int = 30
    # per_source 模式下的 tick 间隔（秒）
    collector_tick_interval_seconds: int = 60
    # 监测关键词（兜底用）：keywords 表已成为采集过滤 + 预警匹配的唯一权威源
    # （见 app/services/keyword_service.py，表空时回退到此配置）。
    # 廊坊市全域视角（廊坊+大厂+三河+香河+固安）。现由 keywords 表驱动，此值仅作应急兜底。
    collector_keywords: str = "廊坊,大厂,大厂回族自治县,三河,香河,固安,舆情,消防,安全生产,民生,投诉"
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
    # 微博采集（Phase Weibo-1 重新启用）：
    # 旧 Playwright 直爬方案已弃用（WeiboCollector 类保留仅为兼容，weibo_cookie 同）。
    # weibo_enabled 现在是 WeiboOctopusCollector（八爪鱼 API）的运行总开关：
    # False 时即使 data_sources 行启用，fetch 也直接跳过（双保险），默认 False。
    weibo_enabled: bool = False
    weibo_cookie: str = ""

    # ===== 八爪鱼开放 API（Phase Weibo-1；仅数据获取，不控制云采集启停）=====
    # 凭据只允许来自环境变量（.env），禁止写入 data_sources.config_json 或硬编码。
    # 方式一（推荐）：BAZHU_USERNAME/BAZHU_PASSWORD -> POST /token 换取 access_token（自动缓存续期）。
    # 方式二：BAZHU_API_KEY 直接作为 Bearer access_token（适合外部代为管理令牌的场景）。
    bazhu_api_key: str = ""
    bazhu_username: str = ""
    bazhu_password: str = ""
    bazhu_base_url: str = "https://openapi.bazhuayu.com"
    # 微博短文采集任务 ID（八爪鱼云端任务）；评论任务后续扩展可复用 config_json 覆盖。
    bazhu_task_id: str = ""
    # 单次拉取「未导出数据」条数上限（八爪鱼单次最大 1000）。
    bazhu_fetch_size: int = 1000
    # 拉取成功后是否回调「确认数据已导出」（幂等由 external_id/url 去重兜底；
    # 置 False 时依赖去重、便于排障重放）。
    bazhu_mark_exported: bool = True

    # ===== MediaCrawler Weibo Phase 1A =====
    # Optional runtime boundary settings; no command is started implicitly.
    media_crawler_root: str = ""
    media_crawler_python: str = ""
    media_crawler_timeout_seconds: int = 900
    media_crawler_browser_data: str = ""
    # Real MediaCrawler subprocesses require an explicit operator opt-in.
    media_crawler_enable_real_run: bool = False
    # Explicit Enable-phase gate. Keep false until an approved enablement step.
    # Environment variable: MEDIA_CRAWLER_REAL_RUN_GATE.
    media_crawler_real_run_gate: bool = False
    # Optional entry file used only by the environment check/manual operator tooling.
    media_crawler_entry: str = ""
    # Deployment-only runtime isolation; never serialized into DataSource config.
    media_crawler_profile_root: str = ""
    # Upstream MediaCrawler checkout root, used as the subprocess cwd. When unset
    # it is derived from the configured entry's parent directory so checkout-
    # relative imports (e.g. open('libs/douyin.js')) resolve. Never serialized.
    media_crawler_checkout_root: str = ""
    media_crawler_login_type: str = "qrcode"
    media_crawler_scheduler_login_type: str = "cookie"

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

    @field_validator("secret_key")
    @classmethod
    def _reject_default_secret_key(cls, v: str) -> str:
        """生产安全门禁（ARCH-01 修复）：禁止以公开默认弱密钥启动。

        若 SECRET_KEY 仍为源码公开默认值 'change-me-in-production'，
        说明生产环境未配置强密钥，启动时直接失败，杜绝认证被绕过。
        """
        if v == "change-me-in-production":
            raise ValueError(
                "SECRET_KEY 仍为公开默认弱值 'change-me-in-production'，"
                "存在认证绕过风险（ARCH-01）。请在生产 .env 中设置强随机密钥"
                "（python -c \"import secrets; print(secrets.token_urlsafe(48))\"）后重试。"
            )
        return v

    @field_validator("init_admin_password")
    @classmethod
    def _warn_empty_init_admin_password(cls, v: str) -> str:
        """ARCH-10 同源残留清理：初始化管理员备用密码安全提示。

        该字段仅在 init_db 首次创建 admin 时使用；为空/未配置时给出明确
        启动提示，要求通过 .env 的 INIT_ADMIN_PASSWORD 显式设置强密码，
        杜绝弱口令兜底。已存在 admin 时不会被写入，不影响现有登录。
        """
        if not v:
            import sys
            print(
                "[SECURITY WARNING] INIT_ADMIN_PASSWORD 为空或未配置；"
                "若需首次初始化管理员，请在 .env 中设置强随机密码，"
                "否则 init_db 不会写入可用的默认凭据。",
                file=sys.stderr,
            )
        return v

    # ===== Grok 实时搜索辅助采集源（Phase Grok-2；仅采集，非 AI 分析）=====
    # API Key 仅来自环境变量（.env 的 GROK_API_KEY），禁止写入 data_sources.config_json 或硬编码。
    grok_api_key: str = ""
    grok_base_url: str = "https://api.x.ai/v1"
    # 模型版本配置化（不写死业务逻辑）；运营方按 xAI 当前可用模型调整（如 grok-4.20 / grok-4.3）。
    grok_model: str = "grok-4.20"
    # 可选显式代理；为空时复用 openai 默认 httpx 客户端（继承 HTTPS_PROXY）。
    grok_proxy: str = ""
    # 单个关键词最多保留的 citation 条数（仅裁剪，不影响 API 调用本身）。
    grok_search_count: int = 5

    # ===== Bocha auxiliary search leads (Phase Bocha-1A; not a Collector) =====
    # API Key is environment-only. Never store it in the database, data_sources.config_json,
    # logs, or frontend responses. Bocha leads do not auto-create Opinion/Event/Alert rows.
    bocha_api_key: str = ""
    bocha_base_url: str = "https://api.bochaai.com/v1"
    bocha_timeout: float = 10.0
    bocha_search_count: int = 8

    # Bocha AI Search is a separate integration.  The credential remains
    # environment-only; these settings are never serialized in API output.
    # When unset, the existing BOCHA_API_KEY is reused for backwards compatibility.
    bocha_ai_api_key: str = ""
    bocha_ai_base_url: str = "https://api.bocha.cn/v1"
    bocha_ai_timeout: float = 30.0
    bocha_ai_search_count: int = 20
    bocha_ai_weibo_domains: str = "weibo.com|m.weibo.cn"
    bocha_ai_xiaohongshu_domains: str = "xiaohongshu.com|xhslink.com"

    # ===== Anspire web search (environment-only credential) =====
    anspire_enabled: bool = False
    anspire_api_key: str = ""
    anspire_base_url: str = "https://plugin.anspire.cn"
    anspire_timeout: float = 20.0
    anspire_default_top_k: int = 10

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


    # ===== Phase 6 可靠性收口配置（集中阈值，禁止散落 magic number）=====
    # P1-1：启动时对账「仍 running 的历史 CollectorRun」的超时阈值（分钟）。
    # 仅回收开始时间早于 now - 该值的记录，避免误判刚启动/仍在途的任务。
    collector_run_zombie_timeout_minutes: int = 60
    # P1-3：后台任务（task_manager._tasks，内存态）终态 TTL 回收（分钟）。
    # 终态（success/failed）任务超过该时长后自动清理，防止内存无限增长。
    task_retention_minutes: int = 120
    # P1-3：后台任务数量硬上限。超限时仅清理最老的终态任务，绝不删除运行中任务。
    task_max_count: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
