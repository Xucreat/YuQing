#!/usr/bin/env python
"""安全启动 PostgreSQL（RBAC-2A 启动可见性增强）。

特点
----
* 数据目录**固定为预期身份基线** ``ExpectedIdentity().data_directory``，
  不接受任何外部参数指向其他目录——从根上杜绝误启 ``YQ\\pgdata`` 之类克隆库。
* 启动前打印 [DATABASE SAFETY CHECK] 预期身份。
* 启动后再次调用门禁校验，确认实例身份 VERIFIED。

用法:
  python backend/scripts/pg_start_safe.py [--port 5432]

依赖环境变量（可选）:
  PG_BIN   PG 二进制目录（默认项目自带 PG 16）
  PGPORT   监听端口
"""
import os
import sys
import time

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.db_identity import ExpectedIdentity, assert_identity_for_migration  # noqa: E402

# PG 二进制目录（项目自带 PG 16）
PG_BIN = os.environ.get("PG_BIN", r"C:\Users\Administrator\Desktop\YQ\pgsql\pgsql\bin")
PG_CTL = os.path.join(PG_BIN, "pg_ctl.exe")
# 数据目录固定为预期基线，禁止外部覆盖——这是安全核心
DATA_DIR = ExpectedIdentity().data_directory
PORT = os.environ.get("PGPORT", "5432")
LOG = os.path.join(os.path.dirname(DATA_DIR), "pg_start_safe.log")


def main() -> int:
    import argparse
    import subprocess

    ap = argparse.ArgumentParser(description="安全启动 PostgreSQL（仅限预期数据目录）")
    ap.add_argument("--port", default=PORT)
    args = ap.parse_args()
    port = args.port

    print("[PG START SAFETY GATE] 目标 data_directory 固定为预期基线:")
    print(f"  {DATA_DIR}")
    if not os.path.isdir(DATA_DIR):
        print(f"[ERROR] 预期数据目录不存在: {DATA_DIR}")
        return 2

    env = os.environ.copy()
    # 干净 PATH，避免 MSYS / 其他 DLL 干扰 pg 子进程
    env["PATH"] = PG_BIN + os.pathsep + r"C:\Windows\System32" + os.pathsep + r"C:\Windows\System32\wbem"

    cmd = [PG_CTL, "-D", DATA_DIR, "-W", "-o", f"-p {port}", "-l", LOG, "start"]
    print("[PG START] 执行:", " ".join(cmd))
    try:
        # 注意：pg_ctl 会 fork 出常驻 postgres 守护进程并继承 stdout/stderr 管道，
        # 若 capture_output 会一直等待管道 EOF 而挂起。因此重定向到 DEVNULL，
        # pg_ctl 自身的启动日志写到 -l 指定的文件。
        proc = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except Exception as e:
        print(f"[ERROR] 启动失败: {e!r}")
        return 2
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    if proc.returncode != 0:
        print(f"[ERROR] pg_ctl 退出码 {proc.returncode}")
        return 2

    # 启动后再次校验身份（断言不匹配会以非零码退出）
    time.sleep(3)
    try:
        assert_identity_for_migration()
        return 0
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2


if __name__ == "__main__":
    sys.exit(main())
