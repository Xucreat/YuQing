"""数据库身份安全门禁（RBAC-2A 引入）。

目的
----
本项目曾发生「误连早期空克隆数据目录」的严重事故：PostgreSQL 被启动到
``YQ\\pgdata``（陈旧克隆，与真实库是同一 cluster 的文件级拷贝），而非真实生产库
``舆情监测系统\\pgdata``，导致业务数据“看似消失”。为防止复发，本模块在**任何高风险
写操作**（``alembic upgrade/downgrade``、``seed``、``init_db``、数据修复脚本）之前，
强制校验当前连接实例是否就是预期的生产数据库。

本环境的关键约束（已实测）
--------------------------
* ``system_identifier`` 可读，但**克隆库与真实库相同**（文件级拷贝时 initdb 已生成，
  拷贝后不变）。因此 ``system_identifier`` 只能用于“检测到完全不同的 cluster”，
  **不能**用于在克隆/真实之间区分。
* ``data_directory`` 在本环境**无法通过 SQL 读取**：数据目录路径含中文
  （``舆情监测系统``），以 GBK 字节存储，而服务器编码为 UTF8，PG 在转换时抛
  ``invalid byte sequence for encoding UTF8``。任何 client_encoding 都无法绕过。
  → 故 ``data_directory`` 仅作“尽力而为”的检查：可读且不匹配才中止；不可读时标记为
    警告并依赖下面的业务指纹。

因此，本环境真正可靠的“克隆/空库”区分信号是**业务数据指纹**
（如 ``opinions`` 表行数）。真实库 opinions≈697，克隆库（误迁移后）业务表为空。
门禁据此判定：业务数据量低于阈值即视为“错误的 / 空的数据库”并中止。

开关
----
* 环境变量 ``DB_IDENTITY_CHECK=off`` 可整体关闭门禁（用于单元测试等已知安全场景）。
* 所有预期值均可通过环境变量覆盖，默认值来自 ``database-environment-baseline.md``。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import Engine, create_engine, text


# ---------------------------------------------------------------------------
# 预期身份基线（项目级安全基线，不依赖端口号）
# ---------------------------------------------------------------------------
DEFAULT_EXPECTED_SYSTEM_IDENTIFIER = "7663057120701798896"
DEFAULT_EXPECTED_DATA_DIRECTORY = r"C:\Users\Administrator\Desktop\舆情监测系统\pgdata"
DEFAULT_EXPECTED_DATABASE = "opinion_db"
# 业务指纹：真实库 opinions 远大于此值；克隆/空库为 0 → 触发中止。
# 仅当连接数据库 == expected.database 时才校验（避免误伤测试库）。
DEFAULT_EXPECTED_MIN_OPINIONS = 100


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _check_enabled() -> bool:
    return _env("DB_IDENTITY_CHECK", "on").lower() not in ("off", "0", "false", "no")


@dataclass
class ExpectedIdentity:
    """预期数据库身份基线。字段为空字符串 / None 表示不检查该项。"""

    system_identifier: str = field(
        default_factory=lambda: _env("EXPECTED_PG_SYSTEM_IDENTIFIER", DEFAULT_EXPECTED_SYSTEM_IDENTIFIER)
    )
    data_directory: str = field(
        default_factory=lambda: _env("EXPECTED_PG_DATA_DIRECTORY", DEFAULT_EXPECTED_DATA_DIRECTORY)
    )
    database: str = field(
        default_factory=lambda: _env("EXPECTED_PG_DATABASE", DEFAULT_EXPECTED_DATABASE)
    )
    # 业务指纹：连接库为 expected.database 时，opinions 行数必须 >= 此值
    min_opinions: Optional[int] = field(
        default_factory=lambda: int(_env("EXPECTED_MIN_OPINIONS", str(DEFAULT_EXPECTED_MIN_OPINIONS)) or 0) or None
    )


@dataclass
class IdentityCheckResult:
    ok: bool = True
    database_url: str = ""
    database: str = ""
    data_directory: str = ""
    system_identifier: str = ""
    alembic_version: str = ""
    opinions_count: Optional[int] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


def _norm_path(p: str) -> str:
    """归一化路径用于跨差异比较（小写 + 规范分隔符 + 去尾部分隔符）。"""
    return os.path.normcase(os.path.normpath(p)).rstrip(os.sep)


def verify_database_identity(
    engine: Engine,
    expected: Optional[ExpectedIdentity] = None,
) -> IdentityCheckResult:
    """连接 engine，读取真实身份并与预期比对。

    本函数本身不抛异常（便于调用方决定如何中止）；连接失败会抛出。
    """
    if expected is None:
        expected = ExpectedIdentity()

    res = IdentityCheckResult(ok=True)
    try:
        with engine.connect() as conn:
            # 当前数据库名
            res.database = conn.execute(text("SELECT current_database()")).scalar() or ""

            # data_directory：尽力而为（本环境不可读，失败仅警告）
            try:
                res.data_directory = conn.execute(text("SHOW data_directory")).scalar() or ""
            except Exception:
                res.data_directory = ""
            if not res.data_directory:
                res.add_warning(
                    "data_directory 在本环境无法通过 SQL 读取（中文路径 GBK/UTF8 编码冲突）；"
                    "已退化为业务指纹校验。"
                )

            # system_identifier：pg_control_system()
            try:
                sid = conn.execute(text("SELECT system_identifier FROM pg_control_system()")).scalar()
                res.system_identifier = str(sid) if sid is not None else ""
            except Exception as e:
                res.system_identifier = f"<unreadable:{type(e).__name__}>"

            # alembic_version
            try:
                res.alembic_version = (
                    conn.execute(text("SELECT version_num FROM alembic_version")).scalar() or ""
                )
            except Exception:
                res.alembic_version = "<no alembic_version table>"

            # 业务指纹：opinions 行数
            try:
                res.opinions_count = conn.execute(text("SELECT count(*) FROM opinions")).scalar()
            except Exception:
                res.opinions_count = None
    except Exception as e:  # 连接失败
        res.ok = False
        res.add_error(f"无法连接数据库: {e!r}")
        return res

    # ---- 比对 ----
    # 1) system_identifier（检测完全不同的 cluster）
    if expected.system_identifier and res.system_identifier != expected.system_identifier:
        res.add_error(
            f"system_identifier 不匹配: 实际={res.system_identifier} 期望={expected.system_identifier}"
        )

    # 2) data_directory（可读且不匹配才中止；不可读仅警告）
    if expected.data_directory and res.data_directory:
        if _norm_path(res.data_directory) != _norm_path(expected.data_directory):
            res.add_error(
                f"data_directory 不匹配: 实际={res.data_directory} 期望={expected.data_directory}"
            )

    # 3) 业务指纹（仅当连接库 == 预期库时校验，避免误伤测试库）
    if (
        expected.min_opinions is not None
        and expected.database
        and res.database == expected.database
    ):
        if res.opinions_count is None:
            res.add_error(
                f"业务指纹校验失败: opinions 表不可读（当前库可能不是预期的生产库 opinion_db）"
            )
        elif res.opinions_count < expected.min_opinions:
            res.add_error(
                f"业务指纹校验失败: opinions 行数={res.opinions_count} 低于阈值 {expected.min_opinions}"
                f"（疑似空库/克隆库/错误数据库，已中止写操作）"
            )

    return res


def print_safety_block(res: IdentityCheckResult, expected: ExpectedIdentity, url: str) -> None:
    print("=" * 64)
    print("[DATABASE SAFETY CHECK]")
    print(f"DATABASE_URL    : {url}")
    print(f"Host           : {_host_of(url)}")
    print(f"Port           : {_port_of(url)}")
    print(f"Database       : {res.database or '(unknown)'}")
    print(f"Data directory : {res.data_directory or '(unreadable in this env)'}")
    print(f"System ident.  : {res.system_identifier or '(unknown)'}")
    print(f"Alembic version: {res.alembic_version or '(unknown)'}")
    print(f"Opinions count : {res.opinions_count if res.opinions_count is not None else '(unknown)'}")
    print("-" * 64)
    print(f"EXPECTED system_identifier : {expected.system_identifier}")
    print(f"EXPECTED data_directory    : {expected.data_directory}")
    print(f"EXPECTED database          : {expected.database}")
    print(f"EXPECTED min_opinions      : {expected.min_opinions}")
    if res.warnings:
        print("WARNINGS:")
        for w in res.warnings:
            print(f"  - {w}")
    if res.errors:
        print("MISMATCH DETAILS:")
        for e in res.errors:
            print(f"  - {e}")
    print("=" * 64)


def assert_identity_for_migration(database_url: Optional[str] = None) -> IdentityCheckResult:
    """在迁移前执行强校验。

    不匹配时打印安全块并以退出码 2 中止进程；匹配时打印 VERIFIED。
    ``DB_IDENTITY_CHECK=off`` 时整体跳过（用于测试等已知安全场景）。
    """
    from app.core.config import settings

    if not _check_enabled():
        print("=" * 64)
        print("[DATABASE SAFETY CHECK] DB_IDENTITY_CHECK=off —— 门禁已跳过（仅限测试/已知安全场景）")
        print("=" * 64)
        r = IdentityCheckResult(ok=True)
        r.add_warning("DB_IDENTITY_CHECK 已关闭，未执行身份校验")
        return r

    url = database_url or settings.database_url
    expected = ExpectedIdentity()
    engine = create_engine(url, pool_pre_ping=True)
    res = verify_database_identity(engine, expected)
    print_safety_block(res, expected, url)
    if not res.ok:
        print("\n[DATABASE IDENTITY: MISMATCH — ABORTED]\n")
        import sys

        sys.exit(2)
    print("\n[DATABASE IDENTITY: VERIFIED]\n")
    return res


def _host_of(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _port_of(url: str) -> str:
    try:
        from urllib.parse import urlparse

        return str(urlparse(url).port or "")
    except Exception:
        return ""
