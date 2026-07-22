"""Event 聚合器（Phase 4-Event-1 重构：成员判定核心逻辑）。

设计目标（来自 Phase 4-Event-0 审计结论）：
  - 当前实现把 Opinion.keywords（内置 16 敏感词字面命中）的交集直接当「同一现实事件」，
    导致大量伪聚合（火灾/事故/投诉/舆情 等通用词跨事件合并）与链式扩散。
  - 本阶段只重构「事件成员判定与聚合核心逻辑」，不引入 Embedding / 向量库 / Redis / MQ，
    不修改 Opinion.keywords 的既有语义，不新增表 / 迁移，不改变 API contract。

核心变化（相对 Phase 3C-0）：
  1. Opinion.keywords 语义保持不变：仍是 RuleFallbackProvider 对「标题+正文」做内置规则词
     命中的结果（纯通用风险标签）。聚合器只把它当作「候选召回信号之一」，并明确标注其局限。
  2. 候选召回 = region_id（行政区划，非精确地点） + 时间窗口 + 可用关键词/信号 + 文本内容。
  3. 成员判定采用「直接判定」而非「并查集传递闭包」：
     - 任意两篇 Opinion 合并需满足直接判定条件（见 _merge_condition）。
     - 聚类为「代表性星型」：新成员必须与所在 Event 的 representative（最高风险成员）
       直接满足判定条件才并入；禁止仅因 A↔B、B↔C 就让 A+B+C 自动同事件（反链式）。
  4. 信号分级：
     - 高区分度信号：来自 ai_keywords（DeepSeek 抽取，若已手动触发）或非内置通用词的关键词。
       当前采集阶段 Opinion.keywords 仅含内置 16 词（全为通用词），故真实数据里高区分度信号
       主要来自「文本相似度」。
     - 低区分度（通用）信号：内置 16 敏感词（火灾/爆炸/事故/伤亡/死亡/冲突/群体/上访/
       维权/投诉/谣言/诈骗/腐败/贪污/涉警/舆情）。共享通用词本身不足以合并，需文本相似度佐证。
  5. 文本相似度：字符 2-gram 余弦（纯 Python，无新依赖），可配置 / 可测试 / 可解释。
  6. 时间约束：新事件候选取最近 event_window_days 天；已有 Event 允许最近新 Opinion 经
     「事件延续」挂载（时间接近 + 至少一个可靠信号 + 文本相似度达阈值），超时不再吸附，
     杜绝「永久吸附」。

约束遵守（与历史一致）：
  - 仅通过 EventOpinion(event_id=..., opinion_id=...) 显式建关联；不使用 relationship.append()，
    不修改关联表结构；event_opinions 表结构不变（无 created_at / unique 约束）。
  - 不写 Event.status（Model 无该列，status 仅 API Schema 层）。
  - 不修改 Opinion / Event / EventOpinion Model、不改数据库结构、不新增 migration。
  - 默认聚合为增量、幂等、不删除历史数据；仅当显式传入 rebuild=True 时才重建近期事件关联
    （且只处理 last_time 在窗口内的「活跃」事件，保留陈旧历史事件，绝不静默全量删除）。
  - dry_run=True 时只计算并返回统计，回滚写操作，供只读验证使用，绝不改动生产数据。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.ai.fallback import DEFAULT_KEYWORDS


# ---------------------------------------------------------------------------
# 通用（低区分度）信号集合：内置 16 敏感词（与 fallback.DEFAULT_KEYWORDS 同源）。
# 这些词是「风险/舆情主题标签」，不是事件唯一标识，单独共享不足以判定同一现实事件。
# ---------------------------------------------------------------------------
GENERIC_KEYWORDS: frozenset[str] = frozenset(w for w, _ in DEFAULT_KEYWORDS)

# 文本相似度：字符 n-gram 长度；中文以 2-gram 为主。
_NGRAM_N: int = 2
# 参与相似度计算的文本上限字符数（标题+正文），避免超长正文拖慢 O(n^2)。
_TEXT_SIM_CAP: int = 300


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _keywords_set(keywords: str) -> set[str]:
    return {k.strip() for k in (keywords or "").split(",") if k.strip()}


def _map_risk_level(max_score: int) -> str:
    """Event.risk_level 映射：>=70 high / >=40 medium / else low。"""
    if max_score >= 70:
        return "high"
    if max_score >= 40:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# 时间 / 文本工具
# ---------------------------------------------------------------------------
def _effective_time(op: Opinion) -> datetime:
    """用于时间相近性判定的时间：优先 publish_time，否则 created_at。"""
    return op.publish_time or op.created_at or _now_utc()


def _time_delta_days(a: Optional[datetime], b: Optional[datetime]) -> float:
    if a is None or b is None:
        return float("inf")
    return abs((a - b).total_seconds()) / 86400.0


def _time_close(a: Optional[datetime], b: Optional[datetime], max_days: int) -> bool:
    return _time_delta_days(a, b) <= max_days


def _ngrams(text: str, n: int = _NGRAM_N) -> set[str]:
    text = re.sub(r"\s+", "", text or "")
    if len(text) == 0:
        return set()
    if len(text) < n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def _cosine_ngram(a: str, b: str) -> float:
    """字符 n-gram 余弦相似度，范围 [0, 1]。"""
    sa, sb = _ngrams(a), _ngrams(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    if inter == 0:
        return 0.0
    return inter / (len(sa) ** 0.5 * len(sb) ** 0.5)


def _opinion_text(op: Opinion) -> str:
    return (op.title or "") + " " + (op.content or "")[:_TEXT_SIM_CAP]


def _text_sim(a: Opinion, b: Opinion) -> float:
    return _cosine_ngram(_opinion_text(a), _opinion_text(b))


# ---------------------------------------------------------------------------
# 信号分级
# ---------------------------------------------------------------------------
def _signals(op: Opinion) -> Tuple[set[str], set[str]]:
    """返回 (高区分度信号集合, 低区分度/通用信号集合)。

    - 高区分度：非内置通用词的关键词，以及 ai_keywords（DeepSeek 抽取，若已配置）。
    - 低区分度：内置 16 敏感词（无论在 keywords 还是 ai_keywords 命中的）。
    当前采集阶段 Opinion.keywords 仅含内置 16 词 -> 实际全部落入「低区分度」。
    因此真实数据聚合的主要判据是「文本相似度」，通用词仅作弱召回。
    """
    kw = _keywords_set(op.keywords)
    ai = _keywords_set(op.ai_keywords)
    all_tokens = kw | ai
    low = all_tokens & GENERIC_KEYWORDS
    high = all_tokens - GENERIC_KEYWORDS
    return high, low


# ---------------------------------------------------------------------------
# 直接成员判定（反链式的关键）
# ---------------------------------------------------------------------------
def _merge_condition(a: Opinion, b: Opinion, cfg=settings) -> bool:
    """判定 a 与 b 是否应直接并入同一 Event。

    硬性门槛：同 region_id + 时间相近（<= event_window_days）。
    满足门槛后，以下任一条件成立才允许合并：
      1) 共享任意「高区分度」信号（具体实体/非通用关键词/ai_keywords）；
      2) 共享「通用」信号 且 文本相似度 >= event_low_merge_text_threshold；
      3) 文本相似度 >= event_text_similarity_threshold（高相似度，单凭文本即可合并）。
    注意：仅共享通用词（条件 2 不满足文本阈值）-> 不合并，杜绝伪聚合。
    """
    if a.region_id != b.region_id:
        return False
    if not _time_close(_effective_time(a), _effective_time(b), cfg.event_window_days):
        return False

    high_a, low_a = _signals(a)
    high_b, low_b = _signals(b)
    sim = _text_sim(a, b)

    if high_a & high_b:
        return True
    if (low_a & low_b) and sim >= cfg.event_low_merge_text_threshold:
        return True
    if sim >= cfg.event_text_similarity_threshold:
        return True
    return False


def _representative(members: List[Opinion]) -> Opinion:
    """取聚类 representative：最高 risk_score，平局取最早有效时间，再平局取最小 id。"""
    return max(
        members,
        key=lambda o: (
            o.risk_score,
            -int(_effective_time(o).timestamp()),
            -o.id,
        ),
    )


# ---------------------------------------------------------------------------
# 纯函数：把一批 Opinion 聚成若干簇（星型 / 反链式，无 DB 依赖，供测试与只读验证复用）
# ---------------------------------------------------------------------------
def cluster_opinions(opinions: List[Opinion], cfg=settings) -> List[List[Opinion]]:
    """代表性星型聚类（确定性：按 risk desc / 时间 asc / id asc 排序后依次入簇）。

    - 每篇 Opinion 与已存在簇的 representative 做 _merge_condition 判定；
    - 命中首个匹配簇即并入（确定性），否则自立新簇；
    - 新成员只对其所在簇的 representative 负责 -> 禁止 A↔B、B↔C 自动推导出 A↔C。
    """
    ordered = sorted(
        opinions,
        key=lambda o: (
            -o.risk_score,
            int(_effective_time(o).timestamp()),
            o.id,
        ),
    )
    clusters: List[dict] = []  # {"rep": Opinion, "members": List[Opinion]}
    for op in ordered:
        target: Optional[dict] = None
        for c in clusters:
            if _merge_condition(op, c["rep"], cfg):
                target = c
                break
        if target is not None:
            target["members"].append(op)
        else:
            clusters.append({"rep": op, "members": [op]})
    return [c["members"] for c in clusters]


# ---------------------------------------------------------------------------
# 聚合器主类
# ---------------------------------------------------------------------------
class EventAggregator:
    """将 Opinion 按可解释规则聚合成 Event（只读既有 Model，不改表结构）。"""

    # ----- 对外接口 -----------------------------------------------------
    def aggregate(
        self,
        db: Session,
        rebuild: bool = False,
        dry_run: bool = False,
    ) -> dict:
        """执行一次聚合，返回统计字典 {"created","updated","linked"}。

        rebuild: 仅重建「活跃」事件（last_time 在 event_window_days 内）的关联，
                 保留陈旧历史事件，绝不静默全量删除。需显式开启。
        dry_run: 只计算与统计，回滚写操作（用于只读验证），不改动生产数据。
        """
        now = _now_utc()
        cutoff = now - timedelta(days=settings.event_window_days)

        # 候选召回：最近窗口内、analysis_status=completed 的全部 Opinion。
        # 不再要求 keywords 非空 —— 文本相似度也可召回（解决「该聚不聚」）。
        opinions = (
            db.query(Opinion)
            .filter(
                Opinion.analysis_status == "completed",
                Opinion.created_at >= cutoff,
            )
            .all()
        )

        # rebuild 模式：仅清理活跃事件的关联（显式、有界、保留历史），随后重算。
        if rebuild:
            self._reset_active_event_links(db, now)

        clusters = cluster_opinions(opinions)

        created = 0
        created_ids: set[int] = set()
        updated_ids: set[int] = set()
        linked = 0

        for cluster in clusters:
            rep = _representative(cluster)
            high_rep, _ = _signals(rep)
            ai_rep = _keywords_set(rep.ai_keywords)
            # 是否物化为独立 Event：多成员 / 含高区分度信号 / 风险够高 / 有 ai_keywords。
            materialize = (
                len(cluster) >= 2
                or bool(high_rep)
                or rep.risk_score >= settings.event_singleton_min_risk
                or bool(ai_rep)
            )

            existing = self._match_existing_event(db, cluster, now)
            if existing is not None:
                n = self._link_all(db, existing.id, cluster)
                if n > 0:
                    updated_ids.add(existing.id)
                    linked += n
                self._recompute_event(db, existing, cluster)
            elif materialize:
                event = self._create_event(db, cluster)
                db.flush()
                created += 1
                created_ids.add(event.id)
                linked += self._link_all(db, event.id, cluster)
            else:
                # 低信号单条 Opinion：不单独建事件，但已可能经延续挂载到既有事件；
                # 若仍未挂载则保持「未关联」状态（避免噪声撑爆事件中心）。
                pass

        if dry_run:
            db.rollback()
            return {
                "created": created,
                "updated": len(updated_ids),
                "linked": linked,
                "dry_run": True,
            }

        db.commit()

        # 触发传播重建（与历史行为一致，异常静默）。
        try:
            from app.services.propagation_service import PropagationService

            for eid in created_ids:
                try:
                    PropagationService.rebuild_for_event(db, eid)
                except ValueError:
                    pass
            for eid in updated_ids:
                try:
                    PropagationService.rebuild_for_event(db, eid)
                except ValueError:
                    pass
        except Exception:
            pass

        return {
            "created": created,
            "updated": len(updated_ids),
            "linked": linked,
        }

    # ----- 既有 Event 匹配（共享成员 / 事件延续）-----------------------
    def _match_existing_event(
        self, db: Session, cluster: List[Opinion], now: datetime
    ) -> Optional[Event]:
        """将簇匹配到既有 Event：

        1) 共享成员：簇中任一 Opinion 已挂到某 Event -> 直接沿用（幂等、防重复创建）；
        2) 事件延续：无共享成员时，若簇 representative 与某「活跃」Event 的 representative
           满足 _merge_condition 且时间接近（<= event_continuation_days），则延续挂载。
        """
        member_ids = {o.id for o in cluster}
        if member_ids:
            linked = (
                db.query(EventOpinion.event_id)
                .filter(EventOpinion.opinion_id.in_(member_ids))
                .limit(1)
                .all()
            )
            if linked:
                return db.get(Event, linked[0].event_id)

        # 事件延续：只看 last_time 在延续窗口内的活跃事件，避免陈旧事件永久吸附。
        rep = _representative(cluster)
        cont_cutoff = now - timedelta(days=settings.event_continuation_days)
        events = (
            db.query(Event)
            .filter(Event.last_time >= cont_cutoff)
            .all()
        )
        rep_cache: dict[int, Opinion] = {}
        for ev in events:
            ev_rep = rep_cache.get(ev.id) or self._event_representative(db, ev, rep_cache)
            # 退化事件（无关联舆情，representative 为 None）直接跳过，避免误判/异常。
            if ev_rep is None:
                continue
            if _time_close(_effective_time(rep), ev.last_time, settings.event_continuation_days):
                if _merge_condition(rep, ev_rep):
                    return ev
        return None

    @staticmethod
    def _event_representative(
        db: Session, event: Event, cache: dict[int, Opinion]
    ) -> Opinion:
        if event.id in cache:
            return cache[event.id]
        rows = (
            db.query(EventOpinion.opinion_id)
            .filter(EventOpinion.event_id == event.id)
            .all()
        )
        oids = [r.opinion_id for r in rows]
        ops = db.query(Opinion).filter(Opinion.id.in_(oids)).all() if oids else []
        rep = _representative(ops) if ops else None
        if rep is not None:
            cache[event.id] = rep
        return rep

    def _reset_active_event_links(self, db: Session, now: datetime) -> None:
        """rebuild 模式：仅删除「活跃」事件（last_time 在窗口内）的 EventOpinion 关联。

        不删除 Event 行本身、不触碰陈旧历史事件，属于显式、有界的重建操作。
        """
        cutoff = now - timedelta(days=settings.event_window_days)
        active = db.query(Event.id).filter(Event.last_time >= cutoff).all()
        active_ids = [r.id for r in active]
        if not active_ids:
            return
        db.query(EventOpinion).filter(
            EventOpinion.event_id.in_(active_ids)
        ).delete(synchronize_session=False)

    # ----- Event 创建 / 更新 --------------------------------------------
    @staticmethod
    def _merge_keywords(cluster: Iterable[Opinion]) -> set[str]:
        merged: set[str] = set()
        for op in cluster:
            merged |= _keywords_set(op.keywords)
        return merged

    @staticmethod
    def _pick_top_risk(cluster: list[Opinion]) -> Opinion:
        return max(cluster, key=lambda o: o.risk_score)

    def _create_event(self, db: Session, cluster: list[Opinion]) -> Event:
        top = self._pick_top_risk(cluster)
        merged_kw = sorted(self._merge_keywords(cluster))
        times = [
            _effective_time(op) for op in cluster if _effective_time(op) is not None
        ]
        # 临时兼容（非最终 Event Narrative 方案）：title / description 暂沿用代表性 Opinion，
        # 待 Phase 4-Event-2 引入生成式标题/摘要时再替换。
        event = Event(
            title=top.title,
            description=(top.content or "")[:200],
            keyword=",".join(merged_kw),
            risk_level=_map_risk_level(max(op.risk_score for op in cluster)),
            opinion_count=len(cluster),
            first_time=min(times) if times else None,
            last_time=max(times) if times else None,
        )
        db.add(event)
        return event

    def _link_all(
        self, db: Session, event_id: int, cluster: list[Opinion]
    ) -> int:
        """显式创建 EventOpinion 关联；已存在则跳过。返回新建关联数（幂等，无重复）。"""
        existing_ids = {
            row.opinion_id
            for row in db.query(EventOpinion)
            .filter(EventOpinion.event_id == event_id)
            .all()
        }
        added = 0
        for op in cluster:
            if op.id in existing_ids:
                continue
            db.add(EventOpinion(event_id=event_id, opinion_id=op.id))
            existing_ids.add(op.id)
            added += 1
        db.flush()  # 立即可见，供同事务内延续匹配读取
        return added

    def _recompute_event(
        self, db: Session, event: Event, _new_cluster: list[Opinion]
    ) -> None:
        """重算 opinion_count / last_time / risk_level / keyword（并集）。"""
        linked = (
            db.query(EventOpinion)
            .filter(EventOpinion.event_id == event.id)
            .all()
        )
        opinion_ids = [row.opinion_id for row in linked]
        opinions = db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).all()
        if not opinions:
            return
        event.opinion_count = len(opinions)
        times = [_effective_time(o) for o in opinions if _effective_time(o) is not None]
        if times:
            event.last_time = max(times)
        event.risk_level = _map_risk_level(max(o.risk_score for o in opinions))
        merged = self._merge_keywords(opinions)
        if merged:
            event.keyword = ",".join(sorted(merged))
