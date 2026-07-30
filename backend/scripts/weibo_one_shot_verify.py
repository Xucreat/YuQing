"""微博数据源一次性真实采集验收驱动（Phase Weibo-1 验收）。

设计约束（来自用户）：
- 不修改 scheduler / 不等待周期任务 / 不影响其他数据源。
- 通过 WeiboOctopusCollector -> CollectorService 的 one-shot 手动调用完成真实采集，
  不依赖 data_sources.weibo_octopus.enabled（保持 false，仅本进程注入采集器）。
- 风险链路（Opinion -> RiskEngine -> Event -> Alert）的 Event/Alert 部分由本脚本
  在验收阶段「一次性手动」触发（与采集器 one-shot 同哲学，非启用调度）。
- 不修改 RiskEngine / Event聚合 / 评分规则，仅调用既有函数。

运行：在 backend/ 下，使用项目 venv：
  DATABASE_URL=... opinion_db ... DB_IDENTITY_CHECK=off \
    .venv/Scripts/python.exe scripts/weibo_one_shot_verify.py
"""
from __future__ import annotations

import json
import logging
import os
import sys

# 允许在 backend/ 下以 `python scripts/weibo_one_shot_verify.py` 运行（导入 app 包）
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from datetime import datetime, timezone

from sqlalchemy import func

from app.core.config import settings
from app.db.session import SessionLocal
from app.collectors.service import CollectorService
from app.collectors.weibo_octopus_collector import WeiboOctopusCollector
from app.models.opinion import Opinion
from app.models.collector_run import CollectorRun
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRecord
from app.services.event.aggregator import auto_aggregate_after_collect, _map_risk_level
from app.services.alert_service import AlertService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("weibo_one_shot_verify")

# 请求钩子：记录是否向 /token 端点发起过请求（用于验证 A：确认走 API Key Bearer，不调 /token）
_request_log = []


def _record_request(resp, *args, **kwargs):
    _request_log.append({"url": resp.url, "method": resp.request.method if resp.request else None})


def attach_token_watch(session):
    session.hooks.setdefault("response", []).append(_record_request)

db = SessionLocal()

result = {"meta": {}, "A_api": {}, "B_collector_run": {}, "C_opinion": {}, "D_chain": {}, "E_quality": {}}

# ---------------------------------------------------------------------------
# 基线
# ---------------------------------------------------------------------------
max_id_before = db.query(func.max(Opinion.id)).scalar() or 0
weibo_before = db.query(Opinion).filter(Opinion.source == "weibo").count()
events_before = db.query(Event).count()
alerts_before = db.query(AlertRecord).count()
run_start = datetime.now(timezone.utc)
result["meta"] = {
    "run_start_utc": run_start.isoformat(),
    "weibo_enabled": settings.weibo_enabled,
    "bazhu_base_url": settings.bazhu_base_url,
    "bazhu_task_id_set": bool(settings.bazhu_task_id),
    "max_opinion_id_before": max_id_before,
    "weibo_opinions_before": weibo_before,
    "events_before": events_before,
    "alerts_before": alerts_before,
}

# ---------------------------------------------------------------------------
# 验证脚本层兼容适配（不动生产代码 weibo_octopus_collector.py）：
# 1) CollectorService._process_collector 对所有采集器统一传 region_kw/topic_kw，
#    而生产采集器 WeiboOctopusCollector.fetch 仅接受 keywords，会抛 TypeError；
#    此处用子类补齐签名使本次真实验收链路跑通。生产 bug 已记录待修复。
# 2) 本次八爪鱼任务字段模板为「博文内容/博主昵称/详情链接/页面网址」，
#    与 DEFAULT_FIELD_MAP 精确键名不匹配（_pick 为精确匹配），在脚本层合并候选名，
#    使真实微博能正确映射落库。生产 DEFAULT_FIELD_MAP 待扩候选。
class WeiboOctopusCollectorVerified(WeiboOctopusCollector):
    def __init__(self, **cfg):
        super().__init__(**cfg)
        # 合并（非替换）候选名，覆盖本次任务字段模板；不丢默认英文候选
        extra = {
            "content": ["博文内容", "微博正文"],
            "title": ["博文内容"],
            "author": ["博主昵称"],
            "url": ["页面网址", "详情链接"],
            "external_id": ["详情链接", "微博id"],
        }
        for k, names in extra.items():
            cur = list(self.field_map.get(k, []))
            for n in names:
                if n not in cur:
                    cur.append(n)
            self.field_map[k] = cur
        # 验收脚本层：不消费八爪鱼未导出队列（mark_exported=False），便于复跑诊断
        self.mark_exported = False

    def fetch(self, keywords=None, region_kw=None, topic_kw=None, **kwargs):
        # 关键词过滤仅用 keywords（全局表驱动）；region_kw/topic_kw 在本采集器语义下忽略
        return super().fetch(keywords=keywords)


# ---------------------------------------------------------------------------
# A. 八爪鱼 API 探针（不入库、不消费未导出标记）
# ---------------------------------------------------------------------------
A = result["A_api"]
A["auth_mode"] = "BAZHU_API_KEY" if settings.bazhu_api_key else "username/password"
try:
    probe = WeiboOctopusCollectorVerified(filter_by_keywords=False, mark_exported=False)
    attach_token_watch(probe.session)
    token = probe._get_token()
    raw_rows = probe._fetch_not_exported(token)
    A["reachable"] = True
    A["token_endpoint_called"] = any("/token" in r["url"] for r in _request_log)
    A["api_key_used_directly"] = bool(settings.bazhu_api_key) and (token == settings.bazhu_api_key)
    A["endpoints_hit"] = sorted({r["url"].split("?")[0] for r in _request_log})
    A["raw_rows"] = len(raw_rows)
    A["sample_keys"] = sorted(list(raw_rows[0].keys())) if raw_rows else []
    mapped = [probe._map_row(r) for r in raw_rows]
    mapped = [m for m in mapped if m]
    A["mapped_rows"] = len(mapped)
    # 字段覆盖（探针全量，不过滤）
    A["field_coverage"] = {
        "external_id": sum(1 for m in mapped if m.get("external_id")),
        "author": sum(1 for m in mapped if m.get("author")),
        "url": sum(1 for m in mapped if m.get("url")),
        "engagement": sum(1 for m in mapped if m.get("engagement")),
        "publish_time": sum(1 for m in mapped if m.get("publish_time")),
    }
    log.info("A. API 探针成功：raw_rows=%d, mapped=%d", A["raw_rows"], A["mapped_rows"])
except Exception as e:  # noqa: BLE001
    A["reachable"] = False
    A["error"] = f"{type(e).__name__}: {e}"[:500]
    log.exception("A. API 探针失败")

# ---------------------------------------------------------------------------
# 1. 一次性真实采集：WeiboOctopusCollector -> CollectorService（注入式，绕过 data_sources）
# ---------------------------------------------------------------------------
svc = CollectorService(collectors=[WeiboOctopusCollectorVerified()], collector_type="weibo")
attach_token_watch(svc.collectors[0].session)
B = result["B_collector_run"]
try:
    collect_result = svc.collect_and_analyze(db, trigger_type="manual")
    B["result"] = {
        "collector_type": collect_result.collector_type,
        "fetched_raw": collect_result.fetched_raw,
        "created": collect_result.created,
        "analyzed": collect_result.analyzed,
        "failed": collect_result.failed,
    }
except Exception as e:  # noqa: BLE001
    B["result"] = {"error": f"{type(e).__name__}: {e}"[:500]}
    B["collection_failed"] = True
    log.exception("1. 一次性采集失败（已容错，继续产出报告）")
# 捕获本次 weibo 的 CollectorRun 审计行
runs = (
    db.query(CollectorRun)
    .filter(CollectorRun.collector_name == "微博", CollectorRun.start_time >= run_start)
    .order_by(CollectorRun.start_time.desc())
    .all()
)
B["runs"] = [
    {
        "id": r.id,
        "collector_name": r.collector_name,
        "status": r.status,
        "fetched_raw": r.fetched_raw,
        "created": r.created,
        "failed": r.failed,
        "error_msg": (r.error_msg or "")[:500],
        "start_time": r.start_time.isoformat() if r.start_time else None,
        "end_time": r.end_time.isoformat() if r.end_time else None,
    }
    for r in runs
]
if not B.get("collection_failed"):
    log.info(
        "1. 采集完成：fetched_raw=%d created=%d analyzed=%d failed=%d",
        collect_result.fetched_raw, collect_result.created, collect_result.analyzed, collect_result.failed,
    )
else:
    log.warning("1. 采集未完成（鉴权/接口失败），跳过汇总日志")

# ---------------------------------------------------------------------------
# C. Opinion 字段校验（本次新增的微博舆情）
# ---------------------------------------------------------------------------
new_weibo = (
    db.query(Opinion)
    .filter(Opinion.id > max_id_before, Opinion.source == "weibo")
    .order_by(Opinion.id)
    .all()
)
C = result["C_opinion"]
C["count"] = len(new_weibo)
bad_source = [o.id for o in new_weibo if o.source != "weibo"]
bad_stype = [o.id for o in new_weibo if o.source_type != "weibo_post"]
C["source_all_weibo"] = len(bad_source) == 0
C["source_type_all_weibo_post"] = len(bad_stype) == 0
C["external_id_present"] = sum(1 for o in new_weibo if o.external_id)
C["author_present"] = sum(1 for o in new_weibo if o.author)
C["engagement_present"] = sum(1 for o in new_weibo if o.engagement)
C["engagement_structure_ok"] = all(
    (o.engagement is None) or (
        isinstance(o.engagement, dict)
        and all(k in ("likes", "comments", "reposts") for k in o.engagement)
        and all(isinstance(v, int) for v in o.engagement.values())
    )
    for o in new_weibo
)
# 抽查样本（最多 10 条）
sample = []
for o in new_weibo[:10]:
    sample.append({
        "id": o.id,
        "title": (o.title or "")[:40],
        "author": o.author,
        "external_id": (o.external_id or "")[:16],
        "url": (o.url or "")[:48],
        "engagement": o.engagement,
        "risk_score": o.risk_score,
        "risk_level": _map_risk_level(o.risk_score) if o.risk_score is not None else None,
        "sentiment": o.sentiment,
        "analysis_status": o.analysis_status,
    })
C["sample"] = sample
log.info("C. 新增微博舆情 %d 条，external_id=%d author=%d engagement=%d",
         len(new_weibo), C["external_id_present"], C["author_present"], C["engagement_present"])

# ---------------------------------------------------------------------------
# D. 风险链路 one-shot 下游：Event 聚合 + Alert 评估（与 scheduler 同函数，非启用调度）
# ---------------------------------------------------------------------------
D = result["D_chain"]
D["events_before"] = events_before
D["alerts_before"] = alerts_before
weibo_ids = [o.id for o in new_weibo]

agg = auto_aggregate_after_collect(SessionLocal)
D["aggregate"] = {k: agg.get(k) for k in ("created", "updated", "linked", "skipped", "reason")}
if agg.get("skipped"):
    log.warning("D. 事件聚合被跳过（另一聚合进行中）：%s；后续由调度器补聚合", agg.get("reason"))

# 关联的 Event（通过 EventOpinion）
event_ids = set()
if weibo_ids:
    eos = db.query(EventOpinion).filter(EventOpinion.opinion_id.in_(weibo_ids)).all()
    event_ids = {eo.event_id for eo in eos if eo.event_id}
D["weibo_linked_event_count"] = len(event_ids)
D["weibo_linked_event_ids"] = sorted(event_ids)[:20]

# Alert 评估（一次性手动，与 scheduler._run_alert_eval_job 一致）
alert_eval = AlertService.evaluate(db)
AlertService.sync_alert_events(db)
D["alert_eval"] = {k: alert_eval.get(k) for k in ("total_checked", "alerts_created")}
weibo_alerts = []
if weibo_ids:
    weibo_alerts = db.query(AlertRecord).filter(AlertRecord.opinion_id.in_(weibo_ids)).all()
D["weibo_alert_count"] = len(weibo_alerts)
D["weibo_alerts_sample"] = [
    {"id": a.id, "rule_name": a.rule_name, "risk_level": a.risk_level,
     "opinion_id": a.opinion_id, "event_id": a.event_id, "status": a.status}
    for a in weibo_alerts[:10]
]
events_after = db.query(Event).count()
alerts_after = db.query(AlertRecord).count()
D["events_after"] = events_after
D["alerts_after"] = alerts_after
D["events_delta"] = events_after - events_before
D["alerts_delta"] = alerts_after - alerts_before
log.info("D. 聚合=%s；weibo 关联事件=%d；告警评估=%s；weibo 告警=%d",
         D["aggregate"], len(event_ids), D["alert_eval"], len(weibo_alerts))

# ---------------------------------------------------------------------------
# E. 数据质量统计（全部微博舆情，含本次新增）
# ---------------------------------------------------------------------------
all_weibo = db.query(Opinion).filter(Opinion.source == "weibo").all()
E = result["E_quality"]
n = len(all_weibo)
empty_content = sum(1 for o in all_weibo if not (o.content or "").strip())
ext_ids = [o.external_id for o in all_weibo if o.external_id]
dup_ext = n - len(set(ext_ids)) if ext_ids else 0
no_url = sum(1 for o in all_weibo if not (o.url or "").strip())
# 风险等级分布（按 risk_score 派生）
risk_dist = {"high": 0, "medium": 0, "low": 0}
for o in all_weibo:
    lvl = _map_risk_level(o.risk_score) if o.risk_score is not None else "low"
    risk_dist[lvl] += 1
E["total"] = n
E["empty_content"] = empty_content
E["empty_content_ratio"] = round(empty_content / n, 4) if n else 0
E["duplicate_external_id"] = dup_ext
E["no_url"] = no_url
E["no_url_ratio"] = round(no_url / n, 4) if n else 0
E["risk_level_distribution"] = risk_dist

# 与已有数据源比较（按 source 聚合）
rows = (
    db.query(Opinion.source, func.count(Opinion.id))
    .group_by(Opinion.source)
    .all()
)
E["by_source"] = {src: cnt for src, cnt in rows}
# 各 source 风险分布
risk_by_src = {}
for src, _ in rows:
    ops = db.query(Opinion).filter(Opinion.source == src).all()
    d = {"high": 0, "medium": 0, "low": 0}
    for o in ops:
        lvl = _map_risk_level(o.risk_score) if o.risk_score is not None else "low"
        d[lvl] += 1
    risk_by_src[src] = d
E["risk_by_source"] = risk_by_src
log.info("E. 微博舆情共 %d 条；空正文=%d；重复external_id=%d；无url=%d；风险分布=%s",
         n, empty_content, dup_ext, no_url, risk_dist)

# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------
out_path = "weibo_acceptance_result.json"
result["meta"]["token_endpoint_called_overall"] = any("/token" in r["url"] for r in _request_log)
result["meta"]["endpoints_hit_overall"] = sorted({r["url"].split("?")[0] for r in _request_log})
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, default=str)
print("\n===== 微博一次性真实采集验收摘要 =====")
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
print(f"\n结果已写入: {out_path}")
db.close()
