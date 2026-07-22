"""Phase C-Event-2 操作脚本：Event 叙事 Backfill（Rule-first + 按需 LLM）。

用法：
  # 生产只读预览（默认，绝不写库）—— 生成本地可审计 JSON/MD 报告
  python scripts/backfill_event_narrative.py
  python scripts/backfill_event_narrative.py --no-llm          # 离线/无余额：LLM 路由跳过真实调用
  python scripts/backfill_event_narrative.py --event-ids 117,118 --limit 10 \
      --report-out _event2_preview --report-format both

  # 对测试库验证写回（需明确 --write；模型失败自动降级规则叙事）
  DATABASE_URL='...:5432/opinion_test' python scripts/backfill_event_narrative.py --write

路由结果类型：RULE_SIMPLE / RULE_TEMPLATE / LLM_REQUIRED
状态类型：rule_simple / rule_template / llm_success / llm_fallback / failed

安全原则：
  - 默认只做 dry-run（只读 SELECT + 回滚），不写任何库。
  - 仅当显式传入 --write 才写回 Event.title / Event.description（仅这两个字段）。
  - 不改变事件成员、Opinion、PropagationNode、AlertRecord 或任何聚合规则。
  - 不重新执行 migrate_events。
本脚本不修改 API contract / 表结构 / Model。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# 必须在导入 app 之前由环境变量 DATABASE_URL 决定目标库（默认指向生产 opinion_db）。
from app.db.session import SessionLocal  # noqa: E402
from app.services.event import narrative as ev_narrative  # noqa: E402


def _render_md(report, results_with_flags) -> str:
    lines = [
        "# Event-2 Narrative Backfill 只读预览报告（Rule-first）",
        "",
        f"- 模式：`{report.mode}`",
        f"- 生成时间(UTC)：{report.generated_at}",
        f"- 选中事件数：{report.total_selected}",
        f"- 已处理：{report.processed}",
        "",
        "## 路由 / 成本统计",
        "",
        f"- 规则直接生成（RULE_SIMPLE）：{report.rule_simple}",
        f"- 规则模板生成（RULE_TEMPLATE）：{report.rule_template}",
        f"- LLM 调用成功（llm_success）：{report.llm_success}",
        f"- LLM 失败回退（llm_fallback）：{report.llm_fallback}",
        f"- 生成失败（failed）：{report.failed}",
        f"- 预计全量 LLM 调用数（若全部调 LLM）：{report.estimated_full_llm_calls}",
        f"- 按路由应调用 LLM 数：{report.estimated_routed_llm_calls}",
        f"- 实际发起 LLM 调用数：{report.actual_llm_calls}",
        f"- 估计节省 token（按每调用 {ev_narrative._EST_TOKENS_PER_LLM_CALL} 估算）：{report.estimated_tokens_saved}",
        f"- 总耗时：{report.duration_ms} ms",
        "",
        "## 逐事件明细",
        "",
        "| event_id | route | status | score | 成员 | llm_called | llm_status | fallback | 耗时(ms) | 质量标记 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in report.results:
        fl = ", ".join(results_with_flags.get(r.event_id, [])) or "-"
        fb = (r.fallback_route or "") if r.status == "llm_fallback" else ""
        lines.append(
            f"| {r.event_id} | {r.route} | {r.status} | {r.complexity_score} "
            f"| {r.member_count} | {str(r.llm_called)} | {r.llm_status or '-'} "
            f"| {fb} | {r.elapsed_ms} | {fl} |"
        )
    lines += ["", "## 拟议叙事（proposed）", ""]
    for r in report.results:
        fl = ", ".join(results_with_flags.get(r.event_id, [])) or "-"
        lines.append(f"### Event {r.event_id}  [{r.status}]  route={r.route}  质量: {fl}")
        lines.append(f"- 当前 title：{(r.current_title or '')[:120]}")
        lines.append(f"- 当前 description：{(r.current_description or '')[:200]}")
        lines.append(f"- **拟议 title**：{r.title}")
        lines.append(f"- **拟议 description**：{r.description}")
        if r.status == "llm_fallback":
            lines.append(f"- fallback 原因：{r.fallback_reason}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Event 叙事 Backfill（Rule-first，默认只读 dry-run）")
    ap.add_argument("--write", action="store_true", help="写回 Event.title/description（必须显式；默认仅 dry-run）")
    ap.add_argument("--event-ids", type=str, default=None, help="逗号分隔的 event_id 白名单")
    ap.add_argument("--limit", type=int, default=None, help="最多处理 N 个事件（按 id 升序）")
    ap.add_argument("--min-interval", type=float, default=2.0, help="每事件间隔秒数（尊重 LLM RPM 限流），0=不等待")
    ap.add_argument("--no-llm", action="store_true", help="跳过真实 LLM 调用（离线/无余额预览）；LLM 路由确定性规则回退")
    ap.add_argument("--force", action="store_true", help="重新生成（即便已有叙事；当前默认即重生成，占位扩展）")
    ap.add_argument("--report-out", default="_event2_preview", help="报告输出目录")
    ap.add_argument(
        "--report-format", choices=["json", "md", "both"], default="both", help="报告格式"
    )
    args = ap.parse_args()

    dry_run = not args.write
    event_ids = None
    if args.event_ids:
        event_ids = [int(x) for x in args.event_ids.split(",") if x.strip()]

    db = SessionLocal()
    try:
        report = ev_narrative.backfill(
            db,
            event_ids=event_ids,
            limit=args.limit,
            dry_run=dry_run,
            write=args.write,
            min_interval=args.min_interval,
            attempt_llm=not args.no_llm,
            force=args.force,
        )
    finally:
        db.close()

    # 质量标记直接取自结果（统一质检），不再重复计算。
    flags_map: dict[int, list[str]] = {r.event_id: r.quality_flags for r in report.results}

    os.makedirs(args.report_out, exist_ok=True)
    payload = report.model_dump()
    # 注入每个事件的复杂度明细便于审计
    for r in payload["results"]:
        r["quality_flags"] = flags_map.get(r["event_id"], [])

    if args.report_format in ("json", "both"):
        with open(os.path.join(args.report_out, "event2_preview.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    if args.report_format in ("md", "both"):
        with open(os.path.join(args.report_out, "event2_preview.md"), "w", encoding="utf-8") as f:
            f.write(_render_md(report, flags_map))

    # 控制台摘要
    print(
        f"[mode={report.mode}] selected={report.total_selected} "
        f"rule_simple={report.rule_simple} rule_template={report.rule_template} "
        f"llm_success={report.llm_success} llm_fallback={report.llm_fallback} "
        f"failed={report.failed} "
        f"routed_llm={report.estimated_routed_llm_calls} actual_llm={report.actual_llm_calls} "
        f"tokens_saved~{report.estimated_tokens_saved} duration={report.duration_ms}ms"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
