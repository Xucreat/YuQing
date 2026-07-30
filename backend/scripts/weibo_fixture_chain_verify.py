"""微博全链路贯通验证（fixture，非真实数据；仅跑测试库 opinion_test，结束清理）。

目的：因八爪鱼任务当前无数据（total=0），无法做真实数据采集下的 C/D/E 验证。
本脚本用「八爪鱼原始字段形状的 fixture 行」经 WeiboOctopusCollector 真实映射
+ CollectorService 真实入库/风险链路 + 真实 Event 聚合 + 真实 Alert 评估，
证明整条链路对 weibo 形状数据无异常、字段映射正确。运行在测试库，结束清理，
不污染生产库。

运行：
  DATABASE_URL=... opinion_test ... DB_IDENTITY_CHECK=off \
    .venv/Scripts/python.exe scripts/weibo_fixture_chain_verify.py
"""
from __future__ import annotations

import json
import logging
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from datetime import datetime, timezone

from sqlalchemy import func, text

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
log = logging.getLogger("weibo_fixture_chain")

# 八爪鱼原始字段形状 fixture（覆盖中英文候选名 + 边界：无 external_id / 无 url / 高风险词）
RAW_FIXTURE = [
    {  # 英文候选名 + 完整互动
        "title": "廊坊某小区物业纠纷获调解", "content": "廊坊某小区因停车问题引发纠纷，经社区调解已妥善解决。",
        "url": "https://weibo.com/123/aaa", "publish_time": "2026-07-27 10:00:00",
        "author": "廊坊网友A", "likes": "120", "comments": "30", "reposts": "5", "mid": "mb1",
    },
    {  # 中文候选名
        "标题": "固安道路施工进展", "正文": "固安县城南路施工已进入收尾阶段，预计下周通车。",
        "链接": "https://weibo.com/123/bbb", "发布时间": "2026-07-27 11:30:00",
        "昵称": "固安发布", "点赞": "88", "评论": "12", "转发": "3", "微博id": "mb2",
    },
    {  # 高风险词（事故/火灾）触发风险评分
        "title": "三河一工厂事故通报", "content": "三河市某工厂发生爆炸事故，造成局部影响，相关部门已介入处置。",
        "url": "https://weibo.com/123/ccc", "publish_time": "2026-07-27 12:00:00",
        "author": "应急头条", "likes": "1.2万", "comments": "450", "reposts": "200", "mid": "mb3",
    },
    {  # 无 external_id（回退 url 去重）
        "title": "香河民生服务升级", "content": "香河县推出多项便民服务，提升群众办事效率。",
        "url": "https://weibo.com/123/ddd", "publish_time": "2026-07-27 13:00:00",
        "author": "香河融媒",
    },
    {  # 无 url（回退 title+publish_time 去重）
        "title": "大厂县文化活动预告", "content": "大厂县将于本周末举办群众文化演出活动，欢迎参与。",
        "publish_time": "2026-07-27 14:00:00", "author": "大厂文旅", "mid": "mb5",
    },
    {  # 普通民生
        "title": "永清县雨情通报", "content": "永清县今日有阵雨，提醒居民注意出行安全。",
        "url": "https://weibo.com/123/fff", "publish_time": "2026-07-27 15:00:00",
        "author": "永清气象", "likes": "10", "mid": "mb6",
    },
    {  # 腐败/上访 高风险词
        "title": "某地信访维稳动态", "content": "网传某项目存在腐败问题，部分群众上访，纪委已介入调查。",
        "url": "https://weibo.com/123/ggg", "publish_time": "2026-07-27 16:00:00",
        "author": "观察者", "mid": "mb7",
    },
    {  # 无任何互动数字
        "title": "文安县政府工作会议", "content": "文安县召开重点工作推进会议，部署下半年任务。",
        "url": "https://weibo.com/123/hhh", "publish_time": "2026-07-27 17:00:00",
        "author": "文安发布", "mid": "mb8",
    },
    {  # 重复 external_id（mb1 复制，验证去重幂等）
        "title": "廊坊某小区物业纠纷获调解", "content": "廊坊某小区因停车问题引发纠纷，经社区调解已妥善解决。",
        "url": "https://weibo.com/123/aaa", "publish_time": "2026-07-27 10:00:00",
        "author": "廊坊网友A", "mid": "mb1",
    },
    {  # 短链 url
        "title": "廊坊交通提示", "content": "廊坊市区部分路段早高峰拥堵，请错峰出行。",
        "url": "https://t.cn/abc123", "publish_time": "2026-07-27 18:00:00",
        "author": "廊坊交警", "mid": "mb10",
    },
    {  # 维权 高风险词
        "title": "消费维权案例", "content": "市民购买家电遇质量问题，经消协调解成功维权。",
        "url": "https://weibo.com/123/jjj", "publish_time": "2026-07-27 19:00:00",
        "author": "消费报道", "mid": "mb11",
    },
    {  # 普通
        "title": "廊坊夜经济观察", "content": "廊坊夜间消费场景不断丰富，带动周边商户营收增长。",
        "url": "https://weibo.com/123/kkk", "publish_time": "2026-07-27 20:00:00",
        "author": "廊坊日报", "mid": "mb12",
    },
]


class FixtureWeiboCollector(WeiboOctopusCollector):
    """用 fixture 原始行经真实 _map_row 映射；不经真实 API。"""

    def fetch(self, keywords=None):
        items = []
        for raw in RAW_FIXTURE:
            m = self._map_row(raw)
            if m:
                items.append(m)
        return items


def main():
    db = SessionLocal()
    max_id_before = db.query(func.max(Opinion.id)).scalar() or 0
    events_before = db.query(Event).count()
    alerts_before = db.query(AlertRecord).count()

    svc = CollectorService(collectors=[FixtureWeiboCollector(filter_by_keywords=False, mark_exported=False)],
                           collector_type="weibo")
    res = svc.collect_and_analyze(db, trigger_type="manual")

    new_ids = [o.id for o in db.query(Opinion).filter(Opinion.id > max_id_before, Opinion.source == "weibo").all()]

    # 字段校验
    new_weibo = db.query(Opinion).filter(Opinion.id.in_(new_ids)).all()
    C = {
        "count": len(new_weibo),
        "source_all_weibo": all(o.source == "weibo" for o in new_weibo),
        "source_type_all_weibo_post": all(o.source_type == "weibo_post" for o in new_weibo),
        "external_id_present": sum(1 for o in new_weibo if o.external_id),
        "author_present": sum(1 for o in new_weibo if o.author),
        "engagement_present": sum(1 for o in new_weibo if o.engagement),
        "engagement_structure_ok": all(
            (o.engagement is None) or (isinstance(o.engagement, dict)
                                       and all(k in ("likes", "comments", "reposts") for k in o.engagement)
                                       and all(isinstance(v, int) for v in o.engagement.values()))
            for o in new_weibo
        ),
        "dedup_ok": (len(new_weibo) < len(RAW_FIXTURE)),  # 重复 mb1 应被去重
        "sample": [{"id": o.id, "title": (o.title or "")[:30], "author": o.author,
                    "external_id": o.external_id, "url": (o.url or "")[:30],
                    "engagement": o.engagement, "risk_score": o.risk_score,
                    "risk_level": _map_risk_level(o.risk_score), "sentiment": o.sentiment,
                    "analysis_status": o.analysis_status} for o in new_weibo[:12]],
    }

    # 下游：Event 聚合 + Alert 评估（与 scheduler 同函数）
    agg = auto_aggregate_after_collect(SessionLocal)
    eos = db.query(EventOpinion).filter(EventOpinion.opinion_id.in_(new_ids)).all()
    event_ids = {eo.event_id for eo in eos if eo.event_id}
    alert_eval = AlertService.evaluate(db)
    AlertService.sync_alert_events(db)
    weibo_alerts = db.query(AlertRecord).filter(AlertRecord.opinion_id.in_(new_ids)).all()

    D = {
        "aggregate": {k: agg.get(k) for k in ("created", "updated", "linked", "skipped", "reason")},
        "weibo_linked_event_count": len(event_ids),
        "weibo_linked_event_ids": sorted(event_ids)[:20],
        "alert_eval": {k: alert_eval.get(k) for k in ("total_checked", "alerts_created")},
        "weibo_alert_count": len(weibo_alerts),
        "weibo_alerts_sample": [{"id": a.id, "rule_name": a.rule_name, "risk_level": a.risk_level,
                                 "opinion_id": a.opinion_id, "event_id": a.event_id, "status": a.status}
                                for a in weibo_alerts[:10]],
        "events_delta": db.query(Event).count() - events_before,
        "alerts_delta": db.query(AlertRecord).count() - alerts_before,
    }

    # 数据质量
    ext_ids = [o.external_id for o in new_weibo if o.external_id]
    E = {
        "total": len(new_weibo),
        "empty_content": sum(1 for o in new_weibo if not (o.content or "").strip()),
        "duplicate_external_id": len(new_weibo) - len(set(ext_ids)) if ext_ids else 0,
        "no_url": sum(1 for o in new_weibo if not (o.url or "").strip()),
        "risk_level_distribution": {"high": sum(1 for o in new_weibo if _map_risk_level(o.risk_score) == "high"),
                                    "medium": sum(1 for o in new_weibo if _map_risk_level(o.risk_score) == "medium"),
                                    "low": sum(1 for o in new_weibo if _map_risk_level(o.risk_score) == "low")},
    }

    out = {"C_opinion": C, "D_chain": D, "E_quality": E,
           "collect_result": {"fetched_raw": res.fetched_raw, "created": res.created,
                              "analyzed": res.analyzed, "failed": res.failed}}
    with open("weibo_fixture_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))

    # 清理：删除测试库中所有 weibo 来源 fixture 数据（含传播节点外键），避免污染测试库
    try:
        wb_ids = [r[0] for r in db.query(Opinion.id).filter(Opinion.source == "weibo").all()]
        if wb_ids:
            db.query(AlertRecord).filter(AlertRecord.opinion_id.in_(wb_ids)).delete(synchronize_session=False)
            db.query(EventOpinion).filter(EventOpinion.opinion_id.in_(wb_ids)).delete(synchronize_session=False)
            # propagation_nodes 外键先行删除
            db.execute(text("DELETE FROM propagation_nodes WHERE opinion_id = ANY(:ids)"),
                       {"ids": wb_ids})
            # 删除现已无关联舆情的孤立事件
            for (eid,) in db.query(Event.id).all():
                if db.query(EventOpinion).filter(EventOpinion.event_id == eid).count() == 0:
                    ev = db.query(Event).filter(Event.id == eid).first()
                    if ev:
                        db.delete(ev)
            db.query(Opinion).filter(Opinion.source == "weibo").delete(synchronize_session=False)
        db.query(CollectorRun).filter(CollectorRun.collector_name == "微博").delete(synchronize_session=False)
        db.commit()
        log.info("清理完成：删除 fixture weibo 舆情 %d 条及其关联", len(wb_ids))
    except Exception as e:  # noqa: BLE001
        db.rollback()
        log.warning("清理部分失败（测试库 fixture 残留可接受）：%s", repr(e))
    db.close()


if __name__ == "__main__":
    main()
