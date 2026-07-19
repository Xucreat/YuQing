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
    # 聚合窗口：仅归并最近 N 天内、analysis_status=completed 且 keywords 非空的 Opinion。
    event_window_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
