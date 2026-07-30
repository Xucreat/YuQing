"""GovernmentCollector 修复后「单源」最终冒烟验证（只读基线的写库验证脚本）。

方式：向 CollectorService 显式注入唯一 GovernmentCollector，调用 collect_and_analyze，
仅触发"大厂县政府网站"单源采集（非全量）。复用的均为生产代码链路：
  fetch(keywords, region_kw, topic_kw) -> 去重 -> 建 Opinion -> 规则 AI 分析。
不调用 auto_aggregate_after_collect（避免事件副作用），仅核查该源自身运行结果。

不修改 service.py / common.py / keyword_service.py / DB 结构 / Option C / 主题词。
"""
from __future__ import annotations

from app.collectors.government_collector import GovernmentCollector
from app.collectors.service import CollectorService
from app.db.session import SessionLocal
from sqlalchemy import text


def main() -> None:
    db = SessionLocal()
    try:
        # ---- 基线 ----
        base_op_max = db.execute(
            text("select coalesce(max(id),0) from opinions")
        ).scalar()
        base_gov_count = db.execute(
            text("select count(*) from opinions where source='大厂县政府网站'")
        ).scalar()
        base_run_max = db.execute(
            text("select coalesce(max(id),0) from collector_runs")
        ).scalar()
        print(f"[基线] opinions.max_id={base_op_max} | 大厂县政府网站已有={base_gov_count} | collector_runs.max_id={base_run_max}")

        # ---- 单源采集（显式注入唯一 GovernmentCollector）----
        print("[触发] CollectorService(collectors=[GovernmentCollector()]).collect_and_analyze(trigger_type='manual')")
        svc = CollectorService(collectors=[GovernmentCollector()])
        result = svc.collect_and_analyze(db, trigger_type="manual")
        print(f"[结果] fetched_raw={result.fetched_raw} created={result.created} "
              f"analyzed={result.analyzed} failed={result.failed}")

        # ---- 核查 collector_runs（该源新增的运行记录）----
        runs = db.execute(text(
            "select id, collector_name, status, fetched_raw, error_msg, start_time, end_time "
            "from collector_runs where id > :b order by id"
        ), {"b": base_run_max}).fetchall()
        print(f"\n[collector_runs] 新增 {len(runs)} 条（应为 1 条大厂县政府网站）")
        for r in runs:
            print(f"  run#{r[0]} name={r[1]} status={r[2]} fetched_raw={r[3]} "
                  f"error_msg={r[4]!r} start={r[5]} end={r[6]}")

        # ---- 核查 opinions（source=大厂县政府网站 新增）----
        new_gov = db.execute(text(
            "select id, title, url, region_id, publish_time from opinions "
            "where id > :b and source='大厂县政府网站' order by id"
        ), {"b": base_op_max}).fetchall()
        print(f"\n[opinions] source=大厂县政府网站 新增 {len(new_gov)} 条")
        for r in new_gov:
            title = (r[1] or "")[:50]
            print(f"  #{r[0]} region_id={r[3]} title={title!r} url={ (r[2] or '')[:60] }")

        # ---- 结论判定 ----
        print("\n==== 结论判定 ====")
        ok = True
        if not runs:
            print("  ✗ 未写入 collector_runs 记录")
            ok = False
        else:
            for r in runs:
                if r[2] != "success":
                    print(f"  ✗ run#{r[0]} status={r[2]}（非 success）")
                    ok = False
                if r[4]:
                    print(f"  ✗ run#{r[0]} error_msg 非空: {r[4]!r}")
                    ok = False
                print(f"  · run#{r[0]} fetched_raw={r[3]}（>0 表示真实抓到文章）")
        print(f"  · 大厂县政府网站新增 opinions = {len(new_gov)}")
        print("  >>> 修复验证:", "PASS ✅" if ok else "FAIL ❌")
    finally:
        db.close()


if __name__ == "__main__":
    main()
