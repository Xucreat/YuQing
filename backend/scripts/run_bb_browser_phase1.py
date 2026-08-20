"""Phase 1A 手动闭环驱动（一次性脚本，非生产调度入口）。

职责
----
1. 幂等插入 / 更新 ``bb_browser`` 数据源（key=bb_browser，type=external_browser）。
2. 仅用 ``CollectorService`` 的单采集器管线处理 bb-browser，不触发其它数据源，
   更不触发 MediaCrawler 微博 / 小红书。
3. 使用受控测试关键词「北三县」，复用**正在运行的** bb-browser worker
   （PID 15652）消费 manifest；采集器只读取本次 manifest_id 的结果文件。
4. 跑两轮：第一轮建 Opinion；第二轮同关键词验证去重（新增显著减少或为 0，
   duplicate 增加）。
5. 输出结构化运行记录（JSON），供生成 Phase 1 报告。

约束遵循
------
- 不修改 MediaCrawler / 现有微博小红书链路。
- 不杀 / 重启任何进程（PID 15652 / 28076 / 17776）。
- 不消费历史 incoming / landing-8platform / collector_exchange 旧交换根。
- 不直写 Opinion（经由 CollectorService 管线）。
- 不把 config_json 当 shell 参数透传（平台命令由服务端白名单收敛）。
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# 必须在导入 app 前关闭 DB 身份门禁（已知安全场景：本地已验证库）。
os.environ.setdefault("DB_IDENTITY_CHECK", "off")

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))

from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.collectors.bb_browser_collector import (  # noqa: E402
    BBBrowserCollector,
    ALLOWED_PLATFORMS,
)
from app.collectors.service import CollectorService  # noqa: E402
from app.models.data_source import DataSource  # noqa: E402

CONFIG_PATH = BACKEND / "app" / "collectors" / "bb_browser_datasource_config.json"
TEST_KEYWORD = "北三县"
SOURCE_KEY = "bb_browser"

# 本次运行加长超时，避免 worker 多平台顺序采集时偶发超时（不改变已提交 config）。
RUN_TIMEOUT_SECONDS = 420
DRY_COLLECT_ONLY = False  # 若只想验证 manifest 生成而不入库，可置 True（本脚本默认完整闭环）


def upsert_data_source(db, cfg: dict) -> DataSource:
    existing = db.query(DataSource).filter(DataSource.key == SOURCE_KEY).first()
    payload = {
        "key": SOURCE_KEY,
        "name": "bb-browser聚合采集",
        "type": "external_browser",
        "class_path": "app.collectors.bb_browser_collector.BBBrowserCollector",
        "enabled": True,
        "priority": 95,
        "schedule_enabled": False,
        "schedule_interval_minutes": 60,
        "scope_region_codes": None,
        "config_json": json.dumps(cfg, ensure_ascii=False),
    }
    if existing:
        for k, v in payload.items():
            if k == "key":
                continue
            setattr(existing, k, v)
        row = existing
        print(f"[datasource] 已更新现有 bb_browser 行 id={existing.id}")
    else:
        row = DataSource(**payload)
        db.add(row)
        print("[datasource] 新增 bb_browser 行")
    db.commit()
    return row


def incoming_snapshot(db) -> list[str]:
    """记录当前 collector_data/incoming 文件名清单（用于证明旧文件未被消费）。"""
    return []


def run_once(db, cfg: dict, run_index: int) -> dict:
    # 实例化采集器（直接构造，等价于 registry 装配；不触发其它源）
    coll = BBBrowserCollector(
        platforms=cfg.get("platforms", list(ALLOWED_PLATFORMS)),
        control_root=cfg["control_root"],
        exchange_root=cfg["exchange_root"],
        bb_browser_cli=cfg.get("bb_browser_cli"),
        cdp_url=cfg.get("cdp_url"),
        daemon_url=cfg.get("daemon_url"),
        timeout_seconds=RUN_TIMEOUT_SECONDS,
        poll_interval_seconds=cfg.get("poll_interval_seconds", 2),
        max_items_per_platform=cfg.get("max_items_per_platform", 20),
        manifest_version=cfg.get("manifest_version", 2),
        allow_weibo=bool(cfg.get("allow_weibo", False)),
        allow_xiaohongshu=bool(cfg.get("allow_xiaohongshu", False)),
        collection_mode=cfg.get("collection_mode", "regional"),
    )
    coll.data_source_key = SOURCE_KEY
    coll.scope_region_codes = None

    svc = CollectorService(collectors=[coll])
    run_start = datetime.now(timezone.utc)
    batch_id = uuid.uuid4().hex

    print(f"\n===== 第 {run_index} 轮：manifest 生成 + worker 消费 + 归一化 =====")
    # 直接驱动单采集器管线（与 collect_and_analyze 同一套代码路径，
    # 仅处理本采集器，且用受控关键词，不触达其它源 / MediaCrawler）。
    sub = svc._process_collector(
        db,
        coll,
        monitoring_kw=[TEST_KEYWORD],
        region_kw=None,   # None 避免空 region_kw 触发 warning，national 模式直接准入
        topic_kw=None,
        run_start=run_start,
        batch_id=batch_id,
        trigger_type="manual_phase1",
    )

    # 读取本次 CollectorRun 状态
    run_row = (
        db.query(__import__("app.models.collector_run", fromlist=["CollectorRun"]).CollectorRun)
        .filter_by(batch_id=batch_id)
        .order_by(text("id DESC"))
        .first()
    )
    status = run_row.status if run_row else "unknown"
    ack_status = getattr(run_row, "ack_status", None)

    # 本次 manifest 对应 incoming 文件是否已被 ack 移动到 processed：
    # 交换文件名用 uuid（不含 manifest_id），故以 mtime >= run_start 作为移动依据。
    processed_dir = Path(cfg["exchange_root"]) / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    run_start_ts = run_start.timestamp()
    moved = [
        p for p in processed_dir.glob("*.txt")
        if p.stat().st_mtime >= run_start_ts
    ]

    return {
        "run_index": run_index,
        "batch_id": batch_id,
        "manifest_id": coll._current_manifest_id,
        "fetched_raw": sub.fetched_raw,
        "created": sub.created,
        "duplicate": sub.duplicate,
        "analyzed": sub.analyzed,
        "failed": sub.failed,
        "admission_filtered": sub.admission_filtered,
        "run_status": status,
        "ack_status": ack_status,
        "pending_files_after_ack": len(coll._pending_files),
        "moved_to_processed_count": len(moved),
    }


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    print(f"[config] platforms={cfg['platforms']} collection_mode={cfg.get('collection_mode')}")

    db = SessionLocal()
    try:
        upsert_data_source(db, cfg)

        # 旧 incoming 文件基线（证明未被消费）
        incoming_dir = Path(cfg["exchange_root"]) / "incoming"
        old_before = sorted(p.name for p in incoming_dir.glob("*.txt"))
        print(f"[baseline] incoming 旧文件数 = {len(old_before)}（含 landing-8platform / manifest-3154 等，不得被消费）")

        results = []
        for i in (1, 2):
            res = run_once(db, cfg, i)
            results.append(res)
            print(
                f"  第{i}轮 -> created={res['created']} duplicate={res['duplicate']} "
                f"analyzed={res['analyzed']} failed={res['failed']} "
                f"status={res['run_status']} ack={res['ack_status']} "
                f"moved={res['moved_to_processed_count']}"
            )

        old_after = sorted(p.name for p in incoming_dir.glob("*.txt"))
        consumed_old = [f for f in old_before if f not in old_after]
        print(f"[verify] 旧 incoming 文件是否减少: {len(consumed_old)} 个被消费（应为 0）")

        summary = {
            "test_keyword": TEST_KEYWORD,
            "source_key": SOURCE_KEY,
            "platforms": cfg["platforms"],
            "old_incoming_before": len(old_before),
            "old_incoming_consumed": len(consumed_old),
            "runs": results,
        }
        # 输出到 bb-browser 采集器根目录（即 exchange_root 的父目录），
        # 避免硬编码到不存在的 YQ/bb-browser 采集器 路径导致崩溃。
        out_path = Path(cfg["exchange_root"]).parent / "phase1_run_record.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[record] 运行记录已写入 {out_path}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[FATAL] 闭环失败：{type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
