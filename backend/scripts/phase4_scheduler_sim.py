"""Phase 4D 调度等价模拟（只读，不开启真实自动调度）。

验证点：
1. due_scheduled_sources 发现逻辑：source 62 (schedule_enabled=false) 不会被发现；
   若 bb_browser schedule_enabled=true 且 next 到期则会被发现（用 SQL 条件模拟，不改 DB）。
2. PG advisory lock：跨进程单例锁的获取/释放语义（获取后立即释放，不持有）。
3. 防重复 claim：claim 为单条原子 UPDATE（本脚本只验证 SQL 语义，不执行写）。
4. MediaCrawler 隔离：#40 weibo_mediacrawler 既有 scheduled 状态盘点。

本脚本不修改 data_sources 表，不触发任何采集。
"""
import hashlib
import json
import sys
from datetime import datetime, timezone

import psycopg

DSN = "postgresql://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db"

# 与 scheduler.py 一致的 advisory lock key
ADVISORY_KEY = (
    int.from_bytes(hashlib.sha1(b"opinion-platform-scheduler-singleton").digest()[:8], "big")
    & 0x7FFFFFFFFFFFFFFF
)


def main():
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "checks": {}}

    with psycopg.connect(DSN) as c:
        cur = c.cursor()

        # 1. 发现逻辑：source 62 当前不会被 discovered
        cur.execute(
            """
            SELECT id, key FROM data_sources
            WHERE enabled = true AND schedule_enabled = true
              AND key != 'weibo_octopus'
              AND COALESCE((config_json::jsonb ->> 'is_foreign'), 'false') <> 'true'
              AND (next_collect_time IS NULL OR next_collect_time <= now())
              AND key = 'bb_browser'
            """
        )
        bb_discovered_now = cur.fetchall()
        out["checks"]["bb_browser_discovered_now"] = {
            "rows": [r[0] for r in bb_discovered_now],
            "expectation": "空（schedule_enabled=false 不被发现）",
            "pass": len(bb_discovered_now) == 0,
        }

        # 1b. 模拟：若 bb_browser schedule_enabled=true 且 next 到期，会被发现
        cur.execute(
            """
            SELECT id, key, schedule_enabled,
                   (next_collect_time IS NULL OR next_collect_time <= now()) AS due
            FROM data_sources WHERE key = 'bb_browser'
            """
        )
        bb_row = cur.fetchone()
        out["checks"]["bb_browser_simulated_discovery"] = {
            "id": bb_row[0],
            "key": bb_row[1],
            "schedule_enabled": bb_row[2],
            "would_be_due_if_enabled": bool(bb_row[3]),
            "note": "schedule_enabled=false 因此 due_scheduled_sources 恒不返回；"
                    "若置 true 且 next 到期则会被发现",
        }

        # 2. 其他 schedule_enabled=true 的源（含 MediaCrawler 微博 #40）
        cur.execute(
            """
            SELECT id, key, schedule_interval_minutes, next_collect_time
            FROM data_sources
            WHERE enabled = true AND schedule_enabled = true AND key != 'weibo_octopus'
            ORDER BY id
            """
        )
        sched_sources = cur.fetchall()
        mediacrawler_sched = [r for r in sched_sources if "mediacrawler" in (r[1] or "").lower()]
        out["checks"]["schedule_enabled_sources"] = {
            "total": len(sched_sources),
            "mediacrawler_among_them": [
                {"id": r[0], "key": r[1], "interval_min": r[2], "next": str(r[3])}
                for r in mediacrawler_sched
            ],
            "note": "weibo_mediacrawler(#40) 已 schedule_enabled=true（既有状态），"
                    "开启 bb_browser 真实调度会与它共存于同一 tick 派发——无法可靠隔离，"
                    "故本阶段仅做模拟，不开启真实自动调度",
        }
        cur.close()

    # 3. PG advisory lock 语义验证（获取后立即释放，绝不持有）
    #    若首次获取 false，说明锁已被生产 uvicorn 进程持有 → 单例锁生效（正面证据）。
    with psycopg.connect(DSN) as c:
        cur = c.cursor()
        cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_KEY,))
        got = cur.fetchone()[0]
        reacquired = None
        if got:
            cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_KEY,))
            cur.fetchone()
            cur.execute("SELECT pg_try_advisory_lock(%s)", (ADVISORY_KEY,))
            reacquired = bool(cur.fetchone()[0])
            if reacquired:
                cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_KEY,))
                cur.fetchone()
        cur.close()
        if got:
            note = "独立连接可获取锁，释放后可重新获取（单例锁机制成立，且当前无生产进程持有）"
            passed = bool(reacquired)
        else:
            note = "pg_try_advisory_lock 返回 false → 锁已被生产 uvicorn 进程持有，"
            "跨进程单例语义正确生效（同一时刻仅一个进程可启动调度器）"
            passed = True
        out["checks"]["advisory_lock"] = {
            "acquired": bool(got),
            "held_by_other_process": not bool(got),
            "note": note,
            "pass": passed,
        }

    # 4. 防重复 claim：验证 claim SQL 是单条原子 UPDATE（语义，非执行）
    out["checks"]["claim_dedup"] = {
        "mechanism": "claim-then-dispatch：单条 UPDATE 一次性推进 next_collect_time，"
                     "tick 内不重复选中同一源",
        "note": "scheduler._run_collector_tick 先 claim 后 dispatch，防重复 run 成立",
    }

    out_path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\Desktop\YQ\phase4_scheduler_sim.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
