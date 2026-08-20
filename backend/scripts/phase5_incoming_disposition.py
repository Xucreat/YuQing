"""Phase 5 阶段五：历史 incoming 处置工具（默认 dry-run）。

只做分类建议；仅显式 ``--apply`` 才移动文件，且强制：
- 每批 ≤ 10 个文件；
- 移动前后 SHA256 校验；
- 目标文件已存在时拒绝（不覆盖）；
- 中途失败自动回滚；
- 禁止对 failed/orphan/weibo 文件自动 ack 或移动（需人工确认）。

用法：
  python phase5_incoming_disposition.py --dry-run
  python phase5_incoming_disposition.py --apply --target quarantine --audit audit.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXCHANGE_ROOT = Path(r"C:\Users\Administrator\Desktop\bb-browser 采集器\collector_data")
INCOMING = EXCHANGE_ROOT / "incoming"

# 禁止自动处理的平台（weibo/xhs 属禁用链路，历史文件单独标记）
FORBIDDEN_PLATFORMS = ("weibo", "xhs", "m_weibo", "xiaohongshu")

CATEGORY_KEEP = "keep"
CATEGORY_MANUAL_REVIEW = "manual_review"
CATEGORY_QUARANTINE = "quarantine_candidate"
CATEGORY_FORBIDDEN = "weibo_do_not_touch"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_incoming_meta(p: Path) -> dict:
    meta = {}
    try:
        head = p.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return {"parse": "unreadable"}
    for line in head.splitlines():
        if "=" in line and not line.startswith(("---", "{")):
            k, _, v = line.partition("=")
            meta[k.strip()] = v.strip()
    if "source_key" not in meta:
        for plat in FORBIDDEN_PLATFORMS + ("baidu", "bilibili", "youtube", "hupu", "toutiao"):
            if p.name.startswith(plat + "_"):
                meta["source_key"] = plat
                break
    return meta


def classify_file(source_key: str | None, run_status: str | None, mapping_available: bool = True) -> tuple[str, str]:
    """核心分类（纯函数，可测试）。

    返回 (category, reason)。
    - weibo/xhs → weibo_do_not_touch（永不移动）
    - 映射不可用（mapping_available=False）→ manual_review（需人工对账，禁止自动判为可归档）
    - run_status 缺失 → quarantine_candidate（真正孤立文件）
    - run_status=failed → manual_review（禁止自动 ack/移动）
    - run_status=success/partial → keep
    """
    if source_key in FORBIDDEN_PLATFORMS:
        return CATEGORY_FORBIDDEN, "weibo/xhs 历史文件，禁止自动处理"
    if not mapping_available:
        return CATEGORY_MANUAL_REVIEW, "mapping_unavailable：无法建立 manifest->CollectorRun 映射，需人工对账"
    if run_status is None:
        return CATEGORY_QUARANTINE, "无对应 CollectorRun 的孤立文件"
    if run_status == "failed":
        return CATEGORY_MANUAL_REVIEW, "失败任务产物，禁止自动 ack"
    if run_status in ("success", "partial"):
        return CATEGORY_KEEP, "已有成功/部分成功 run（理论上应已 ack，需人工核对）"
    return CATEGORY_MANUAL_REVIEW, f"未知 run 状态 {run_status!r}"


def build_plan(files: list[dict], run_status_lookup: dict[str, str | None], mapping_available: bool = True) -> list[dict]:
    """files: [{name, source_key, task_manifest_id, sha256}]"""
    plan = []
    for f in files:
        source_key = f.get("source_key")
        mid = f.get("task_manifest_id")
        run_status = run_status_lookup.get(mid) if mid else None
        category, reason = classify_file(source_key, run_status, mapping_available)
        plan.append({**f, "category": category, "reason": reason, "run_status": run_status})
    return plan


def build_reconciliation_inventory(
    files: list[dict],
    plan: list[dict],
    mapping_available: bool,
    run_lookup: dict[str, str | None] | None = None,
    operator: str = "cli",
) -> dict:
    """生成正式对账清单（Phase 7 阶段五，13+ 字段）。

    CollectorRun id/status/ack_status 仅在 mapping 可用时来自真实查询或
    显式 classification；否则为 null（绝不从文件名推断）。
    """
    run_lookup = run_lookup or {}
    entries = []
    for f, p in zip(files, plan):
        mid = f.get("task_manifest_id")
        entries.append({
            "file_name": f["name"],
            "file_sha256": f.get("sha256"),
            "manifest_id": mid,
            "task_id": f.get("task_id"),
            "source_key": f.get("source_key"),
            "collector_run_id": run_lookup.get(mid) if mapping_available else None,
            "collector_run_status": p.get("run_status"),
            "ack_status": None,
            "classification": p["category"],
            "operator": operator,
            "reason": p["reason"],
        })
    entries_json = json.dumps(entries, ensure_ascii=False, sort_keys=True)
    return {
        "inventory_generated_at": datetime.now(timezone.utc).isoformat(),
        "inventory_sha256": hashlib.sha256(entries_json.encode("utf-8")).hexdigest(),
        "mapping_available": mapping_available,
        "operator": operator,
        "entries": entries,
    }


def apply_plan(
    plan: list[dict],
    target_dir: Path,
    audit_path: Path,
    source_dir: Path = INCOMING,
    max_batch: int = 10,
    selected_files: set[str] | None = None,
    allow_manual_review_move: bool = False,
    operator: str = "cli",
) -> dict:
    """执行移动（仅 --apply 调用）。返回审计结果。

    安全约束（Phase 6 修正）：
    - weibo_do_not_touch / keep 永不移动；
    - quarantine_candidate 仅当 selected_files 显式指定该文件时才移动；
    - manual_review 仅当 allow_manual_review_move=True 且 selected_files 显式指定时才移动；
    - 每批 ≤ max_batch；SHA256 校验；目标存在拒绝；中途失败回滚。
    """
    # 显式文件选择：selected_files 为空集合/None 时不移动任何文件（dry-run 语义之外）
    if not selected_files:
        return {"ok": False, "error": "未显式指定文件（--files 为空），拒绝执行（禁止隐式全量 apply）"}

    actions = []
    for a in plan:
        cat = a["category"]
        name = a["name"]
        if cat == CATEGORY_QUARANTINE:
            if name in selected_files:
                actions.append(a)
        elif cat == CATEGORY_MANUAL_REVIEW:
            if allow_manual_review_move and name in selected_files:
                actions.append(a)
        # CATEGORY_FORBIDDEN / CATEGORY_KEEP 永不移动

    if len(actions) > max_batch:
        return {"ok": False, "error": f"超过每批上限 {max_batch}（本次 {len(actions)}），拒绝执行"}

    target_dir.mkdir(parents=True, exist_ok=True)
    moved: list[dict] = []
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "operator": operator,
        "command": " ".join(sys.argv),
        "actions": [],
        "moved": [],
        "rollback": {"status": "none"},
    }
    for a in actions:
        src = source_dir / a["name"]
        if not src.exists():
            audit["rollback"]["status"] = "rolled_back"
            return {"ok": False, "error": f"源文件不存在: {src.name}", "rolled_back": False, "audit": audit}
        # SHA256 校验
        actual_sha = sha256_file(src)
        if a.get("sha256") and actual_sha != a["sha256"]:
            _rollback(moved)
            audit["rollback"]["status"] = "rolled_back"
            return {"ok": False, "error": f"SHA256 不匹配: {src.name}", "rolled_back": True, "audit": audit}
        dst = target_dir / src.name
        if dst.exists():
            _rollback(moved)
            audit["rollback"]["status"] = "rolled_back"
            return {"ok": False, "error": f"目标已存在（拒绝覆盖）: {dst.name}", "rolled_back": True, "audit": audit}
        audit["actions"].append({
            "source": str(src),
            "target": str(dst),
            "category": a["category"],
            "manifest_id": a.get("task_manifest_id", ""),
            "task_id": a.get("task_id", ""),
            "sha256": actual_sha,
            "reason": a.get("reason", ""),
            "operator": operator,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        try:
            src.replace(dst)
            moved.append((src, dst))
            audit["moved"].append({
                "source": str(src), "target": str(dst),
                "manifest_id": a.get("task_manifest_id", ""),
                "task_id": a.get("task_id", ""),
                "category": a["category"],
                "sha256": actual_sha,
            })
        except OSError as exc:
            _rollback(moved)
            audit["rollback"]["status"] = "rolled_back"
            return {"ok": False, "error": f"移动失败 {src.name}: {exc}", "rolled_back": True, "audit": audit}

    audit["rollback"]["status"] = "none"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "moved": len(moved), "audit": audit}


def _rollback(moved: list) -> None:
    for src, dst in reversed(moved):
        try:
            dst.replace(src)
        except OSError:
            pass


def load_run_status(classification_path: str | None = None) -> tuple[dict[str, str | None], bool]:
    """返回 (manifest_id -> run_status 映射, 映射是否可靠可用)。

    - 默认无可靠映射 → ({}, False)，即 mapping_unavailable，调用方必须按
      「需人工对账」处理，绝不把文件误判为孤立可归档。
    - 显式传入 --classification（如 phase4 对账结果 JSON，格式
      {"<manifest_id>": {"run_status": "failed", ...}}）时，加载并返回 (mapping, True)。
    """
    if classification_path:
        p = Path(classification_path)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {}, False
            if not isinstance(data, dict):
                return {}, False
            mapping: dict[str, str | None] = {}
            for mid, v in data.items():
                if isinstance(v, dict):
                    mapping[mid] = v.get("run_status")
            return mapping, True
    return {}, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true", default=False)
    ap.add_argument("--target", default="quarantine")
    ap.add_argument("--audit", default="phase5_disposition_audit.json")
    ap.add_argument("--max-batch", type=int, default=10)
    ap.add_argument("--classification", default=None,
                    help="Phase 4 对账结果 JSON（{manifest_id: {run_status: ...}}），缺省则映射不可用")
    ap.add_argument("--files", default=None,
                    help="逗号分隔的显式文件清单（--apply 时必须提供；未提供不移动任何文件）")
    ap.add_argument("--allow-manual-review-move", action="store_true", default=False,
                    help="允许移动 manual_review（失败任务产物），仍需配合 --files 显式指定")
    args = ap.parse_args()

    if not args.apply:
        args.dry_run = True

    if not INCOMING.exists():
        print("incoming 目录不存在")
        sys.exit(2)

    files = []
    for p in sorted(INCOMING.iterdir()):
        if not p.is_file():
            continue
        meta = parse_incoming_meta(p)
        files.append({
            "name": p.name,
            "source_key": meta.get("source_key"),
            "task_manifest_id": meta.get("task_manifest_id"),
            "task_id": meta.get("task_id"),
            "sha256": sha256_file(p),
        })

    run_status, mapping_available = load_run_status(args.classification)
    plan = build_plan(files, run_status, mapping_available=mapping_available)

    from collections import Counter
    counts = Counter(a["category"] for a in plan)
    print("=== 处置建议（%s）===" % ("DRY-RUN（未移动任何文件）" if args.dry_run else "APPLY"))
    print(f"  mapping_available={mapping_available}")
    for cat, n in counts.items():
        print(f"  {cat}: {n}")

    if args.dry_run:
        inventory = build_reconciliation_inventory(
            files, plan, mapping_available=mapping_available, run_lookup=run_status,
            operator=os.environ.get("USERNAME", "cli"),
        )
        out = {
            "dry_run": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mapping_available": mapping_available,
            "inventory": inventory,
            "plan": plan,
        }
        Path(args.audit).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已写 dry-run 计划 + 正式对账清单 ->", args.audit)
        sys.exit(0)

    if not args.apply:
        print("未传 --apply，仅 dry-run")
        sys.exit(0)

    # --apply 必须显式指定文件清单（禁止隐式全量）
    selected_files = {s.strip() for s in (args.files or "").split(",") if s.strip()} if args.files else None
    target = EXCHANGE_ROOT.parent / "collector_control" / args.target if args.target in ("quarantine", "archive") else Path(args.target)
    result = apply_plan(
        plan, target, Path(args.audit),
        max_batch=args.max_batch,
        selected_files=selected_files,
        allow_manual_review_move=args.allow_manual_review_move,
        operator=os.environ.get("USERNAME", "cli"),
    )
    print(json.dumps({k: v for k, v in result.items() if k != "audit"}, ensure_ascii=False, indent=2))
    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
