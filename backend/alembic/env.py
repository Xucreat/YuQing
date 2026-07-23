"""Alembic 环境配置（绑定 ORM metadata）。"""
from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.core.db_identity import assert_identity_for_migration  # RBAC-2A 安全门禁
from app.db.base import Base

import app.models  # noqa: F401  确保全部模型注册到 Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从配置读取数据库连接（.env -> settings.database_url），不硬编码
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config, pool

    # === 数据库身份安全门禁（RBAC-2A）===
    # 任何实际迁移执行前，强制校验当前实例身份（system_identifier / data_directory）。
    # 不匹配立即以非零码退出，阻止误连错误数据目录。
    assert_identity_for_migration()

    section = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
