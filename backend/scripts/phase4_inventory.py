"""Phase 4 交换目录只读盘点工具。

只读遍历 collector_control / collector_data 全部交换目录，逐文件记录：
路径、大小、mtime、SHA256，并对 incoming/rejected 文件解析 manifest/task/source 元数据。

输出结构见 main()。本脚本不修改、不删除、不移动任何文件。
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXCHANGE_ROOT = Path(r"C:\Users\Administrator\Desktop\bb-browser 采集器\collector_data")
CONTROL_ROOT = Path(r"C:\Users\Administrator\Desktop\bb-browser 采集器\collector_control")

MANIFEST_ID_RE = re.compile(r"[0-9a-f]{32}")
TASK_ID_RE = re.compile(r"([0-9a-f]{32}-rule-[0-9a-z-]+)")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def file_meta(p: Path) -> dict:
    st = p.stat()
    return {
        "name": p.name,
        "size": st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        "sha256": sha256(p),
    }


def parse_incoming(p: Path) -> dict:
    """解析 incoming 记录文件的元数据头（BB_BROWSER_RECORD_VERSION=1 格式）。"""
    meta = {}
    try:
        head = p.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return {"parse": "unreadable"}
    for line in head.splitlines():
        if "=" in line and not line.startswith(("---", "{")):
            k, _, v = line.partition("=")
            meta[k.strip()] = v.strip()
    # 从文件名兜底 source_key
    if "source_key" not in meta:
        name = p.name
        for plat in ("baidu", "bilibili", "youtube", "hupu", "toutiao", "weibo", "xhs"):
            if name.startswith(plat + "_"):
                meta["source_key"] = plat
                break
    return meta


def list_dir(d: Path, parse_meta: bool = False) -> list[dict]:
    if not d.exists():
        return []
    out = []
    for f in sorted(d.iterdir()):
        if f.is_dir():
            continue
        rec = file_meta(f)
        if parse_meta:
            rec["meta"] = parse_incoming(f)
        out.append(rec)
    return out


def main():
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "exchange_root": str(EXCHANGE_ROOT),
        "control_root": str(CONTROL_ROOT),
        "directories": {},
    }
    snapshot["directories"]["incoming"] = {
        "path": str(EXCHANGE_ROOT / "incoming"),
        "files": list_dir(EXCHANGE_ROOT / "incoming", parse_meta=True),
    }
    snapshot["directories"]["processed"] = {
        "path": str(EXCHANGE_ROOT / "processed"),
        "files": list_dir(EXCHANGE_ROOT / "processed"),
    }
    snapshot["directories"]["failed"] = {
        "path": str(EXCHANGE_ROOT / "failed"),
        "files": list_dir(EXCHANGE_ROOT / "failed"),
    }
    snapshot["directories"]["processing"] = {
        "path": str(EXCHANGE_ROOT / "processing"),
        "files": list_dir(EXCHANGE_ROOT / "processing"),
    }
    for name in ("outgoing", "rejected", "stale", "ack_pending", "recovery", "archive"):
        snapshot["directories"][name] = {
            "path": str(CONTROL_ROOT / name),
            "files": list_dir(CONTROL_ROOT / name),
        }

    counts = {k: len(v["files"]) for k, v in snapshot["directories"].items()}
    snapshot["counts"] = counts

    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\Administrator\Desktop\YQ\phase4_directory_inventory.json")
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))
    print("written ->", out_path)


if __name__ == "__main__":
    main()
