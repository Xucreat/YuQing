"""Phase 5 阶段六：安全扫描测试（防明文凭据回归）。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"

# 硬编码凭据赋值模式（排除环境变量读取）
_HARDCODED_RE = re.compile(
    r"^\s*(PASSWORD|PASSWD|SECRET|SECRET_KEY|API_KEY|ACCESS_TOKEN|TOKEN)\s*=\s*[\"'][^\"']{6,}[\"']",
    re.IGNORECASE,
)


def test_no_hardcoded_credentials_in_scripts():
    offenders = []
    for py in SCRIPTS_DIR.glob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            if _HARDCODED_RE.search(line):
                offenders.append(f"{py.name}:{line.strip()[:80]}")
    assert not offenders, f"发现硬编码凭据：{offenders}"


def test_gray_run_script_uses_env_var():
    p = SCRIPTS_DIR / "_phase2_gray_run.py"
    text = p.read_text(encoding="utf-8", errors="ignore")
    assert "os.environ.get(\"YQ_ADMIN_PASSWORD\")" in text or "os.environ.get('YQ_ADMIN_PASSWORD')" in text
    # 不再硬编码旧密码
    assert "k3LBK8" not in text


def test_no_bare_password_assignment_in_scripts():
    for py in SCRIPTS_DIR.glob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"PASSWORD\s*=\s*([\"'][^\"']+[\"'])", text, re.IGNORECASE):
            val = m.group(1)
            # 只允许环境变量读取或空值
            assert "os.environ" in val or val in ("\"\"", "''"), f"{py.name} 疑似硬编码密码: {val[:40]}"


def test_gray_run_script_has_credential_gate():
    """Phase 6 凭据门禁：真实灰度脚本在未轮换凭据时必须拒绝运行。"""
    p = SCRIPTS_DIR / "_phase2_gray_run.py"
    text = p.read_text(encoding="utf-8", errors="ignore")
    # 检测未处理凭据备份文件
    assert ".env.bak_20260806_152704" in text
    # 需显式 --ack-credentials-rotated 才能绕过
    assert "--ack-credentials-rotated" in text
    # 仍拒绝空/硬编码口令
    assert "未设置环境变量 YQ_ADMIN_PASSWORD" in text
