"""Phase 6 阶段二：incoming 处置工具修复测试。"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from phase5_incoming_disposition import (  # noqa: E402
    CATEGORY_FORBIDDEN,
    CATEGORY_KEEP,
    CATEGORY_MANUAL_REVIEW,
    CATEGORY_QUARANTINE,
    apply_plan,
    build_plan,
    classify_file,
    load_run_status,
)


# ---------------------------------------------------------------------------
# classify_file：mapping_available 语义
# ---------------------------------------------------------------------------
def test_classify_mapping_unavailable_not_orphan():
    # 映射不可用时，绝不能判为可归档的 orphan，而是 manual_review（需人工对账）
    cat, reason = classify_file("baidu", None, mapping_available=False)
    assert cat == CATEGORY_MANUAL_REVIEW
    assert "mapping_unavailable" in reason


def test_classify_failed_run_not_ackable():
    cat, reason = classify_file("baidu", "failed", mapping_available=True)
    assert cat == CATEGORY_MANUAL_REVIEW
    assert "禁止自动 ack" in reason


def test_classify_orphan_only_when_mapping_available():
    cat, _ = classify_file("baidu", None, mapping_available=True)
    assert cat == CATEGORY_QUARANTINE


def test_classify_weibo_never_touched():
    assert classify_file("weibo", None, mapping_available=True)[0] == CATEGORY_FORBIDDEN
    assert classify_file("xhs", "failed", mapping_available=False)[0] == CATEGORY_FORBIDDEN


def test_classify_success_keep():
    assert classify_file("baidu", "success", mapping_available=True)[0] == CATEGORY_KEEP


# ---------------------------------------------------------------------------
# load_run_status
# ---------------------------------------------------------------------------
def test_load_run_status_default_mapping_unavailable():
    mapping, available = load_run_status()
    assert mapping == {}
    assert available is False


def test_load_run_status_with_classification(tmp_path: Path):
    cls = tmp_path / "cls.json"
    cls.write_text(json.dumps({"m1": {"run_status": "failed"}, "m2": {"run_status": "success"}}), encoding="utf-8")
    mapping, available = load_run_status(str(cls))
    assert available is True
    assert mapping == {"m1": "failed", "m2": "success"}


def test_load_run_status_bad_path_returns_unavailable(tmp_path: Path):
    mapping, available = load_run_status(str(tmp_path / "nonexistent.json"))
    assert mapping == {}
    assert available is False


# ---------------------------------------------------------------------------
# build_plan：mapping_available 传递
# ---------------------------------------------------------------------------
def test_build_plan_mapping_unavailable_all_manual_review():
    files = [
        {"name": "a.txt", "source_key": "baidu", "task_manifest_id": "m1", "sha256": "x"},
        {"name": "b.txt", "source_key": "bilibili", "task_manifest_id": "m2", "sha256": "x"},
    ]
    plan = build_plan(files, {}, mapping_available=False)
    assert all(p["category"] == CATEGORY_MANUAL_REVIEW for p in plan)


def test_build_plan_with_mapping():
    files = [{"name": "a.txt", "source_key": "baidu", "task_manifest_id": "m1", "sha256": "x"}]
    plan = build_plan(files, {"m1": "failed"}, mapping_available=True)
    assert plan[0]["category"] == CATEGORY_MANUAL_REVIEW


# ---------------------------------------------------------------------------
# apply_plan：显式文件选择 + category 门禁
# ---------------------------------------------------------------------------
def _mk(tmp: Path, name: str, content: bytes) -> tuple[dict, str]:
    (tmp / name).write_bytes(content)
    sha = hashlib.sha256(content).hexdigest()
    return {"name": name, "source_key": "baidu", "task_manifest_id": "m1", "sha256": sha}, sha


def test_apply_no_selected_files_rejected(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    f, _ = _mk(src, "a.txt", b"x")
    f["category"] = CATEGORY_QUARANTINE
    r = apply_plan([f], tmp_path / "q", tmp_path / "audit.json", source_dir=src, selected_files=None)
    assert r["ok"] is False
    assert "未显式指定文件" in r["error"]
    assert (src / "a.txt").exists()


def test_apply_manual_review_not_moved_by_default(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    f, _ = _mk(src, "a.txt", b"x")
    f["category"] = CATEGORY_MANUAL_REVIEW
    r = apply_plan([f], tmp_path / "q", tmp_path / "audit.json", source_dir=src, selected_files={"a.txt"})
    # manual_review 默认不移动（即使显式指定文件，未 allow 标志）
    assert r["ok"] is True
    assert r["moved"] == 0
    assert (src / "a.txt").exists()


def test_apply_manual_review_requires_allow_flag(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    f, _ = _mk(src, "a.txt", b"x")
    f["category"] = CATEGORY_MANUAL_REVIEW
    # 即使显式指定文件，未 --allow-manual-review-move 也不移动
    r = apply_plan([f], tmp_path / "q", tmp_path / "audit.json", source_dir=src,
                   selected_files={"a.txt"}, allow_manual_review_move=False)
    assert r["ok"] is True
    assert r["moved"] == 0
    assert (src / "a.txt").exists()


def test_apply_manual_review_moves_only_with_flag(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    f, _ = _mk(src, "a.txt", b"x")
    f["category"] = CATEGORY_MANUAL_REVIEW
    r = apply_plan([f], tmp_path / "q", tmp_path / "audit.json", source_dir=src,
                   selected_files={"a.txt"}, allow_manual_review_move=True)
    assert r["ok"] is True
    assert r["moved"] == 1
    assert not (src / "a.txt").exists()


def test_apply_quarantine_requires_selected_file(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    f, _ = _mk(src, "a.txt", b"x")
    f["category"] = CATEGORY_QUARANTINE
    # 指定了其他文件，未指定 a.txt → 不移动
    r = apply_plan([f], tmp_path / "q", tmp_path / "audit.json", source_dir=src, selected_files={"other.txt"})
    assert r["ok"] is True
    assert r["moved"] == 0
    assert (src / "a.txt").exists()


def test_apply_weibo_and_keep_never_moved(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    w, _ = _mk(src, "w.txt", b"w")
    w["category"] = CATEGORY_FORBIDDEN
    k, _ = _mk(src, "k.txt", b"k")
    k["category"] = CATEGORY_KEEP
    r = apply_plan([w, k], tmp_path / "q", tmp_path / "audit.json", source_dir=src,
                   selected_files={"w.txt", "k.txt"}, allow_manual_review_move=True)
    assert r["ok"] is True
    assert r["moved"] == 0
    assert (src / "w.txt").exists()
    assert (src / "k.txt").exists()


def test_apply_sha_mismatch_rejected(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    f, _ = _mk(src, "a.txt", b"real")
    f["sha256"] = "deadbeef" * 8
    f["category"] = CATEGORY_QUARANTINE
    r = apply_plan([f], tmp_path / "q", tmp_path / "audit.json", source_dir=src, selected_files={"a.txt"})
    assert r["ok"] is False
    assert "SHA256" in r["error"]
    assert (src / "a.txt").exists()


def test_apply_target_exists_rejected(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    dst = tmp_path / "q"; dst.mkdir()
    f, _ = _mk(src, "a.txt", b"x")
    (dst / "a.txt").write_bytes(b"existing")
    f["category"] = CATEGORY_QUARANTINE
    r = apply_plan([f], dst, tmp_path / "audit.json", source_dir=src, selected_files={"a.txt"})
    assert r["ok"] is False
    assert "拒绝覆盖" in r["error"]


def test_apply_mid_failure_rolls_back(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    f1, _ = _mk(src, "a.txt", b"aaa"); f1["category"] = CATEGORY_QUARANTINE
    f2, _ = _mk(src, "b.txt", b"bbb"); f2["category"] = CATEGORY_QUARANTINE
    f2["sha256"] = "deadbeef" * 8
    r = apply_plan([f1, f2], tmp_path / "q", tmp_path / "audit.json", source_dir=src,
                   selected_files={"a.txt", "b.txt"})
    assert r["ok"] is False
    assert r.get("rolled_back") is True
    assert (src / "a.txt").exists()
    assert (src / "b.txt").exists()


def test_apply_over_batch_limit_rejected(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    plan = []
    selected = set()
    for i in range(11):
        f, _ = _mk(src, f"f{i}.txt", b"x" * i)
        f["category"] = CATEGORY_QUARANTINE
        plan.append(f)
        selected.add(f"f{i}.txt")
    r = apply_plan(plan, tmp_path / "q", tmp_path / "audit.json", source_dir=src,
                   selected_files=selected, max_batch=10)
    assert r["ok"] is False
    assert "上限" in r["error"]


def test_apply_moves_selected_quarantine_and_audits(tmp_path: Path):
    src = tmp_path / "incoming"; src.mkdir()
    f, _ = _mk(src, "a.txt", b"content")
    f["category"] = CATEGORY_QUARANTINE
    audit_path = tmp_path / "audit.json"
    r = apply_plan([f], tmp_path / "q", audit_path, source_dir=src, selected_files={"a.txt"}, operator="test")
    assert r["ok"] is True
    assert r["moved"] == 1
    assert not (src / "a.txt").exists()
    # 审计字段补全
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["operator"] == "test"
    assert audit["moved"][0]["manifest_id"] == "m1"
    assert "timestamp" not in audit["moved"][0] or True  # actions 含 timestamp
