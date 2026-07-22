"""Event-2 Narrative Backfill（Phase C-Event-2）：Rule-first + 按需 LLM。

为已正确重建的 Event 生成高质量、可重复、可观测的事件叙事，
写回 Event.title / Event.description 两个既有字段（不新增 DB 列、不改 API contract）。

改造目标（相对上一阶段「LLM 优先、失败 fallback」）：
- Rule-first：简单事件永远不调用 LLM；
- Complexity-aware：用可解释、可测试、不依赖 LLM 的复杂度评分做路由；
- LLM-on-demand：仅当复杂度达阈值才调用 LLM，负责规则模板会明显生硬的多主题事件；
- 无余额环境（DeepSeek 402/未配置）：LLM 路由失败可靠 fallback 到规则，绝不伪造成功。

设计约束（来自用户 Phase C 范围边界）：
- 只修改 Event 的 title / description（叙事字段），不改变事件成员归属。
- 不修改 Opinion / EventOpinion / PropagationNode / AlertRecord。
- 不改变 event_singleton_min_risk / event_window_days / cluster_opinions 等聚合规则。
- 不重新执行事件迁移（migrate_events）。
- Backfill 幂等：规则生成字节级确定；重复执行结果一致、可观测。
- 失败可观测、可重试，禁止静默吞异常。
- 复用现有 DeepSeek 基础设施（唯一 LLM 路径），不引入第二套调用封装。
- 复杂度主题信号复用 aggregator._cosine_ngram（已测试纯函数），不重写相似度算法。

叙事契约：
- 仅基于该 Event 已确定的 EventOpinion 成员生成（防跨事件错误合并）。
- 构建 prompt 时脱敏：只用 title / summary / keywords / risk_score / sentiment / source（平台名），
  绝不把 content / url / region_id / 作者身份放入模型输入。
- title ≤ 120 字；description ≤ 500 字（硬截断）。
- 单成员 / 多成员均有确定性规则生成器，保证可重复、可审计。
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.schemas.event_narrative import EventNarrative
# 复用聚合器已测试的字符 n-gram 余弦相似度（不重写相似度算法）。
from app.services.event.aggregator import _cosine_ngram

logger = logging.getLogger(__name__)

# 长度硬上限（远低于 DB 列上限 String(512) / Text，留给人类可读空间）。
TITLE_MAX: int = 120
DESC_MAX: int = 500

# 标题软上限：与 check_narrative_quality 的 title_too_long(>80) 阈值对齐，
# 组合标题（具体标题 + 等N条相关舆情聚集）超出时，对具体标题做省略号截断，避免误报质量标记。
TITLE_SOFT_MAX: int = 80

# 复杂度路由阈值（已由生产 84 Event 真实分布只读验证：阈值=5 时仅 4 个事件进 LLM，节省 95%）。
LLM_THRESHOLD: int = 5

# 排序用时间哨兵（None 时间排在最前，保证确定性）。
_TIME_SENTINEL = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 路由枚举
# ---------------------------------------------------------------------------
class ComplexityRoute(str, Enum):
    RULE_SIMPLE = "RULE_SIMPLE"      # 单成员：直接规则生成，0 LLM
    RULE_TEMPLATE = "RULE_TEMPLATE"  # 中等复杂度：模板+统计，0 LLM
    LLM_REQUIRED = "LLM_REQUIRED"    # 复杂：调用 LLM（成功=llm_success，失败=llm_fallback）


# ---------------------------------------------------------------------------
# 上下文（脱敏后的成员事实，供 prompt 与 fallback 共用）
# ---------------------------------------------------------------------------
class MemberFact(BaseModel):
    index: int
    title: str = ""
    summary: str = ""
    keywords: str = ""
    risk_score: int = 0
    sentiment: str = "neutral"
    source: str = ""
    time: str = ""


class EventNarrativeContext(BaseModel):
    event_id: int
    risk_level: str
    opinion_count: int
    first_time: Optional[str] = None
    last_time: Optional[str] = None
    keywords: str = ""
    members: List[MemberFact] = Field(default_factory=list)

    @property
    def members_block(self) -> str:
        """把成员事实格式化为可读文本块，用于 prompt。"""
        if not self.members:
            return "（无关联舆情）"
        lines: List[str] = []
        for m in self.members:
            lines.append(
                f"- 第{m.index}条：标题={m.title or '（无标题）'}；"
                f"摘要={m.summary or '（无摘要）'}；"
                f"来源平台={m.source or '未知'}；"
                f"发布时间={m.time or '未知'}；"
                f"风险分={m.risk_score}；情感={m.sentiment}；"
                f"关键词={m.keywords or '无'}"
            )
        return "\n".join(lines)

    def to_llm_dict(self) -> dict:
        return {
            "risk_level": self.risk_level,
            "opinion_count": self.opinion_count,
            "first_time": self.first_time,
            "last_time": self.last_time,
            "keywords": self.keywords,
            "members_block": self.members_block,
        }


def _effective_time(op: Opinion) -> Optional[datetime]:
    return op.publish_time or op.created_at


def build_context(db: Session, event: Event) -> EventNarrativeContext:
    """从 Event + 其 EventOpinion 成员构建脱敏上下文（只读查询，绝不写库）。"""
    links = (
        db.query(EventOpinion).filter(EventOpinion.event_id == event.id).all()
    )
    oids = [r.opinion_id for r in links]
    ops = db.query(Opinion).filter(Opinion.id.in_(oids)).all() if oids else []
    # 确定性排序：有效时间升序，平局按 id 升序（即时间顺序输入）。
    ops_sorted = sorted(
        ops,
        key=lambda o: (_effective_time(o) or _TIME_SENTINEL, o.id),
    )
    members: List[MemberFact] = []
    for i, o in enumerate(ops_sorted, 1):
        et = _effective_time(o)
        members.append(
            MemberFact(
                index=i,
                title=o.title or "",
                summary=o.summary or "",
                keywords=o.keywords or "",
                risk_score=o.risk_score,
                sentiment=o.sentiment or "neutral",
                source=o.source or "",
                time=et.isoformat() if et else "",
            )
        )
    return EventNarrativeContext(
        event_id=event.id,
        risk_level=event.risk_level,
        opinion_count=event.opinion_count or len(members),
        first_time=event.first_time.isoformat() if event.first_time else None,
        last_time=event.last_time.isoformat() if event.last_time else None,
        keywords=event.keyword or "",
        members=members,
    )


# ---------------------------------------------------------------------------
# Layer 1：确定性规则（单成员）—— 0 LLM
# ---------------------------------------------------------------------------
def generate_simple_rule(context: EventNarrativeContext) -> EventNarrative:
    """单成员事件：用真实标题 + 真实摘要（或脱敏模板）。绝不虚构、绝不取 content 前 200 字。"""
    members = context.members
    if not members:
        raise ValueError("事件无关联舆情，无法生成叙事")
    m = members[0]
    title = (m.title or "").strip() or f"{context.risk_level}风险舆情"
    title = title[:TITLE_MAX]
    if m.summary and m.summary.strip():
        desc = m.summary.strip()[:DESC_MAX]
    else:
        parts = [f"{m.source or '未知来源'}于{m.time or '未知时间'}发布舆情"]
        if context.keywords:
            parts.append(f"涉及关键词：{context.keywords}")
        parts.append(f"风险等级：{context.risk_level}。")
        desc = "".join(parts)[:DESC_MAX]
    return EventNarrative(title=title, description=desc)


# ---------------------------------------------------------------------------
# Layer 2：模板 + 统计（多成员中等复杂度）—— 0 LLM
# ---------------------------------------------------------------------------
def _representative_title(members: List[MemberFact]) -> str:
    """取一条具体（非空）标题作为事件标题的代表；优先最早（members 已按时间升序）。"""
    for m in members:
        t = (m.title or "").strip()
        if t:
            return t
    return ""


def _build_cluster_title(members: List[MemberFact], risk_level: str) -> str:
    """多成员事件标题：『一条具体标题 + 等N条相关舆情聚集』。

    示例：「河北多举措推进基础教育扩优提质等2条相关舆情聚集」。
    - 代表性标题取最早一条非空标题（确定性，且与描述锚点一致）；
    - 组合后超过 TITLE_SOFT_MAX 时，将该具体标题用省略号截断：
      「河北多举措推进基础…等2条相关舆情聚集」；
    - 全部标题为空时降级为不含风险等级的「共N条相关舆情聚集」
      （风险等级仍保留在描述中，不再以「（risk风险）」形式出现在标题）。
    """
    n = len(members)
    suffix = f"等{n}条相关舆情聚集"
    rep = _representative_title(members)
    if not rep:
        # 兜底：无可用标题，不使用「（risk风险）」形式；风险等级见描述。
        return f"共{n}条相关舆情聚集"[:TITLE_MAX]
    if len(rep) + len(suffix) <= TITLE_SOFT_MAX:
        return (rep + suffix)[:TITLE_MAX]
    # 截断具体标题：预留 1 个省略号（…）与 suffix 长度
    budget = TITLE_SOFT_MAX - len(suffix) - 1
    if budget < 1:
        return suffix[:TITLE_MAX]
    return (rep[:budget] + "…" + suffix)[:TITLE_MAX]


def generate_template_rule(context: EventNarrativeContext) -> EventNarrative:
    """多成员事件：模板 + 统计信息 + 代表性 Opinion 标题。基于真实字段拼装，无虚构。"""
    members = context.members
    if not members:
        raise ValueError("事件无关联舆情，无法生成叙事")

    # 去重来源平台
    sources: List[str] = []
    seen = set()
    for m in members:
        if m.source and m.source not in seen:
            seen.add(m.source)
            sources.append(m.source)

    title = _build_cluster_title(members, context.risk_level)
    title = title[:TITLE_MAX]

    parts = [
        f"该事件由 {len(members)} 条舆情组成，"
        f"时间跨度为 {context.first_time or '未知'} 至 {context.last_time or '未知'}，"
        f"风险等级为 {context.risk_level}。"
    ]
    if sources:
        parts.append("涉及来源平台：" + "、".join(sources) + "。")
    if context.keywords:
        parts.append("主要关键词：" + context.keywords + "。")
    first_m = members[0]
    if first_m.title:
        parts.append(f"最早相关舆情为：《{first_m.title[:60]}》。")
    desc = "".join(parts)[:DESC_MAX]
    return EventNarrative(title=title, description=desc)


# ---------------------------------------------------------------------------
# 复杂度分析器（可解释 / 可测试 / 不依赖 LLM / 不随机）
# ---------------------------------------------------------------------------
def _member_score(n: int) -> int:
    return {1: 0, 2: 1, 3: 2, 4: 3}.get(n, 4)


def _source_score(n_src: int) -> int:
    return 0 if n_src <= 1 else (2 if n_src == 2 else 3)


def _time_score(span_days: float) -> int:
    if span_days < 1.0:
        return 0
    if span_days < 3.0:
        return 1
    return 2


def _risk_spread_score(spread: int) -> int:
    if spread < 20:
        return 0
    if spread < 40:
        return 1
    return 2


def _sentiment_score(n_sent: int) -> int:
    return 0 if n_sent <= 1 else (1 if n_sent == 2 else 2)


def _topic_score(avg_title_sim: float) -> int:
    """主题差异：基于成员两两标题相似度（复用 _cosine_ngram）。
    - 高相似（重复转载）→ 0（模板即可）
    - 中等 → 1
    - 明显不同（同簇多主题）→ 2（倾向 LLM 归纳）
    """
    if avg_title_sim >= 0.60:
        return 0
    if avg_title_sim >= 0.30:
        return 1
    return 2


def classify_complexity(context: EventNarrativeContext):
    """返回 (route, score, detail)。detail 为各特征分数字典，供审计与测试。"""
    members = context.members
    n = len(members)
    n_src = len({m.source for m in members if m.source})
    times = [datetime.fromisoformat(m.time) for m in members if m.time]
    span = (max(times) - min(times)).total_seconds() / 86400.0 if times else 0.0
    rs = [m.risk_score for m in members]
    spread = (max(rs) - min(rs)) if rs else 0
    n_sent = len({m.sentiment for m in members if m.sentiment})

    # 标题两两相似度（平均）
    if n >= 2:
        pairs = 0
        s = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                pairs += 1
                s += _cosine_ngram(members[i].title[:120], members[j].title[:120])
        avg_sim = s / pairs if pairs else 1.0
    else:
        avg_sim = 1.0

    detail = {
        "member": _member_score(n),
        "source": _source_score(n_src),
        "time": _time_score(span),
        "risk": _risk_spread_score(spread),
        "sentiment": _sentiment_score(n_sent),
        "topic": _topic_score(avg_sim),
        "avg_title_sim": round(avg_sim, 3),
        "member_count": n,
        "source_count": n_src,
        "time_span_days": round(span, 3),
        "risk_spread": spread,
    }
    score = sum(v for k, v in detail.items() if k in (
        "member", "source", "time", "risk", "sentiment", "topic"))

    if n == 1:
        route = ComplexityRoute.RULE_SIMPLE
    elif score >= LLM_THRESHOLD:
        route = ComplexityRoute.LLM_REQUIRED
    else:
        route = ComplexityRoute.RULE_TEMPLATE
    return route, score, detail


# ---------------------------------------------------------------------------
# 统一质量检查（规则与 LLM 同标准）
# ---------------------------------------------------------------------------
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_JSON_RE = re.compile(r"```|^\s*[\{\}\[\]]|[\{\}\[\]].*:.*[\{\}\[\]]", re.MULTILINE)
_PROMPT_LEAK_RE = re.compile(
    r"作为\s*(一个|一名|AI|人工智能|人工智能助手|语言模型|大模型)|AI助手|语言模型|大模型\b",
    re.IGNORECASE,
)
_FABRICATE_RE = re.compile(
    r"引发广泛关注|舆论持续发酵|持续发酵|网友热议|引发热议|轩然大波|社会各界高度关注",
    re.IGNORECASE,
)
_TEMPLATE_VAR_RE = re.compile(r"\{[^{}]*\}|__[A-Z_]+__")


def check_narrative_quality(title: str, description: str) -> List[str]:
    """统一质量检查：规则与 LLM 生成都执行。返回质量标记列表（可空）。"""
    flags: List[str] = []
    t = title or ""
    d = description or ""
    if not t.strip():
        flags.append("empty_title")
    if not d.strip():
        flags.append("empty_description")
    if len(t) > 80:
        flags.append("title_too_long(>80)")
    if len(d) < 10:
        flags.append("desc_too_short(<10)")
    if _URL_RE.search(t) or _URL_RE.search(d):
        flags.append("possible_url_leak")
    if _JSON_RE.search(t) or _JSON_RE.search(d):
        flags.append("possible_json_fragment")
    if _PROMPT_LEAK_RE.search(t) or _PROMPT_LEAK_RE.search(d):
        flags.append("possible_prompt_leak")
    if _TEMPLATE_VAR_RE.search(t) or _TEMPLATE_VAR_RE.search(d):
        flags.append("unresolved_template_var")
    if _FABRICATE_RE.search(t) or _FABRICATE_RE.search(d):
        flags.append("possible_fabrication")
    return flags


# ---------------------------------------------------------------------------
# 编排器：路由 → 规则直出 / LLM 按需 → 失败 fallback → 统一质检
# ---------------------------------------------------------------------------
class NarrativeResult(BaseModel):
    event_id: int
    status: str  # rule_simple | rule_template | llm_success | llm_fallback | failed
    title: str = ""
    description: str = ""
    member_count: int = 0
    route: str = ""                  # RULE_SIMPLE | RULE_TEMPLATE | LLM_REQUIRED
    complexity_score: int = 0
    complexity_detail: Dict[str, object] = Field(default_factory=dict)
    llm_called: bool = False
    llm_status: Optional[str] = None  # success | failed | skipped | None
    token_usage: Dict[str, object] = Field(default_factory=dict)
    fallback_route: Optional[str] = None  # LLM 失败时回退到的规则路由
    fallback_reason: Optional[str] = None
    error_type: Optional[str] = None
    quality_flags: List[str] = Field(default_factory=list)
    elapsed_ms: int = 0
    current_title: Optional[str] = None  # 写回前的原始值（供 diff）
    current_description: Optional[str] = None


def generate_event_narrative(
    context: EventNarrativeContext,
    llm_callable: Optional[Callable[[EventNarrativeContext], EventNarrative]] = None,
    attempt_llm: bool = True,
) -> NarrativeResult:
    """为单个事件生成叙事（Rule-first）。

    - RULE_SIMPLE / RULE_TEMPLATE：直接规则生成，绝不调用 LLM（llm_called=False）。
    - LLM_REQUIRED：调用 llm_callable（默认 DeepSeek）；成功=llm_success，
      任何失败（402/超时/解析/校验/空/类型错）一律降级到 generate_template_rule，
      如实标记 llm_fallback + fallback_reason；仅当规则回退自身也失败才标 failed。
    - attempt_llm=False：LLM_REQUIRED 也跳过真实调用，直接确定性规则回退
      （用于无余额/离线 Preview，llm_status="skipped"），不影响其他事件。
    """
    if llm_callable is None:
        def _default(ctx: EventNarrativeContext) -> EventNarrative:
            from app.services.ai.providers.deepseek import DeepSeekProvider
            return DeepSeekProvider().generate_event_narrative(ctx.to_llm_dict())
        llm_callable = _default

    route, score, detail = classify_complexity(context)
    t0 = time.perf_counter()

    def _fail(reason: str, etype: str) -> NarrativeResult:
        return NarrativeResult(
            event_id=context.event_id,
            status="failed",
            title="",
            description="",
            member_count=context.opinion_count,
            route=route.value,
            complexity_score=score,
            complexity_detail=detail,
            fallback_reason=reason[:300],
            error_type=etype,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
        )

    # ---- 规则直出（不经 LLM） ----
    if route in (ComplexityRoute.RULE_SIMPLE, ComplexityRoute.RULE_TEMPLATE):
        gen = generate_simple_rule if route == ComplexityRoute.RULE_SIMPLE else generate_template_rule
        try:
            nar = gen(context)
        except Exception as exc:  # noqa: BLE001
            return _fail(f"规则生成失败: {exc}", type(exc).__name__)
        flags = check_narrative_quality(nar.title, nar.description)
        return NarrativeResult(
            event_id=context.event_id,
            status="rule_simple" if route == ComplexityRoute.RULE_SIMPLE else "rule_template",
            title=nar.title,
            description=nar.description,
            member_count=context.opinion_count,
            route=route.value,
            complexity_score=score,
            complexity_detail=detail,
            llm_called=False,
            llm_status=None,
            quality_flags=flags,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
        )

    # ---- LLM 按需 ----
    if not attempt_llm:
        # 无余额 / 离线预览：跳过真实调用，确定性回退，如实标记
        try:
            nar = generate_template_rule(context)
        except Exception as exc:  # noqa: BLE001
            return _fail(f"LLM 跳过时规则回退亦失败: {exc}", type(exc).__name__)
        flags = check_narrative_quality(nar.title, nar.description)
        return NarrativeResult(
            event_id=context.event_id,
            status="llm_fallback",
            title=nar.title,
            description=nar.description,
            member_count=context.opinion_count,
            route=route.value,
            complexity_score=score,
            complexity_detail=detail,
            llm_called=False,
            llm_status="skipped",
            fallback_route=ComplexityRoute.RULE_TEMPLATE.value,
            fallback_reason="llm disabled (--no-llm / offline preview)",
            quality_flags=flags,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
        )

    try:
        nar = llm_callable(context)
        if not isinstance(nar, EventNarrative):
            raise TypeError(f"LLM 返回类型非法：{type(nar).__name__}，期望 EventNarrative")
        title = (nar.title or "").strip()
        desc = (nar.description or "").strip()
        if not title or not desc:
            raise ValueError("LLM 返回空标题或空描述")
        nar = EventNarrative(title=title[:TITLE_MAX], description=desc[:DESC_MAX])
        flags = check_narrative_quality(nar.title, nar.description)
        return NarrativeResult(
            event_id=context.event_id,
            status="llm_success",
            title=nar.title,
            description=nar.description,
            member_count=context.opinion_count,
            route=route.value,
            complexity_score=score,
            complexity_detail=detail,
            llm_called=True,
            llm_status="success",
            token_usage={},  # 真实 token 用量由 LLM provider 透传（当前环境无成功调用）
            quality_flags=flags,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 — 统一捕获降级，但如实记录
        logger.warning("Event %s LLM 叙事失败，降级规则叙事：%s", context.event_id, exc)
        try:
            fb = generate_template_rule(context)
        except Exception as fexc:  # noqa: BLE001
            return _fail(f"LLM 失败且规则回退亦失败: {str(fexc)[:200]}", type(fexc).__name__)
        flags = check_narrative_quality(fb.title, fb.description)
        return NarrativeResult(
            event_id=context.event_id,
            status="llm_fallback",
            title=fb.title,
            description=fb.description,
            member_count=context.opinion_count,
            route=route.value,
            complexity_score=score,
            complexity_detail=detail,
            llm_called=True,
            llm_status="failed",
            fallback_route=ComplexityRoute.RULE_TEMPLATE.value,
            fallback_reason=str(exc)[:300],
            error_type=type(exc).__name__,
            quality_flags=flags,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
        )


# ---------------------------------------------------------------------------
# Backfill 编排：dry-run / write、过滤、限流、可观测
# ---------------------------------------------------------------------------
# 估算：每个被路由跳过（不调用）的 LLM 事件节省的 token（仅作统计假设，清晰标注）。
_EST_TOKENS_PER_LLM_CALL: int = 800  # 假设：每事件 LLM 输入~600 + 输出~200 token


class BackfillReport(BaseModel):
    mode: str
    generated_at: str
    total_selected: int = 0
    processed: int = 0
    rule_simple: int = 0
    rule_template: int = 0
    llm_success: int = 0
    llm_fallback: int = 0
    failed: int = 0
    skipped: int = 0
    # 成本/路由统计
    estimated_full_llm_calls: int = 0      # 若全部事件都调 LLM
    estimated_routed_llm_calls: int = 0    # 按路由本应调用 LLM 的事件数
    actual_llm_calls: int = 0              # 实际发起的 LLM 调用数
    estimated_tokens_saved: int = 0        # (full - routed) * 估算每调用 token
    duration_ms: int = 0
    results: List[NarrativeResult] = Field(default_factory=list)


def backfill(
    db: Session,
    *,
    event_ids: Optional[List[int]] = None,
    limit: Optional[int] = None,
    dry_run: bool = True,
    write: bool = False,
    min_interval: float = 2.0,
    llm_callable: Optional[Callable[[EventNarrativeContext], EventNarrative]] = None,
    attempt_llm: bool = True,
    force: bool = False,
) -> BackfillReport:
    """对一批 Event 执行叙事 backfill。

    默认 dry_run=True：只计算叙事、收集结果、回滚，绝不写库。
    write=True 且 dry_run=False：写回 event.title / event.description（仅这两个字段）。
    不修改 EventOpinion / Opinion / PropagationNode / AlertRecord / 其他 Event 字段。

    attempt_llm=False：即便路由为 LLM_REQUIRED 也跳过真实调用（离线/无余额预览）。
    """
    t_start = time.perf_counter()
    mode = "write" if (write and not dry_run) else "dry_run"

    q = db.query(Event)
    if event_ids:
        q = q.filter(Event.id.in_(event_ids))
    q = q.order_by(Event.id.asc())
    events = q.all()
    if limit is not None:
        events = events[:limit]

    results: List[NarrativeResult] = []
    try:
        for ev in events:
            try:
                ctx = build_context(db, ev)
            except Exception as exc:  # noqa: BLE001
                results.append(
                    NarrativeResult(
                        event_id=ev.id,
                        status="failed",
                        title="",
                        description="",
                        member_count=ev.opinion_count or 0,
                        fallback_reason=f"context 构建失败: {str(exc)[:200]}",
                        error_type=type(exc).__name__,
                        elapsed_ms=0,
                    )
                )
                continue

            res = generate_event_narrative(
                ctx, llm_callable=llm_callable, attempt_llm=attempt_llm)
            res.current_title = ev.title
            res.current_description = ev.description

            if mode == "write":
                try:
                    ev.title = res.title
                    ev.description = res.description
                    db.flush()
                except Exception as exc:  # noqa: BLE001
                    res.status = "failed"
                    res.fallback_reason = f"写入失败: {str(exc)[:200]}"
                    res.error_type = type(exc).__name__
                    logger.error("Event %s 写回失败：%s", ev.id, exc)

            results.append(res)

            if min_interval and min_interval > 0:
                time.sleep(min_interval)
    finally:
        if mode == "write":
            try:
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                logger.error("Backfill 批量提交失败，已回滚：%s", exc)
                for r in results:
                    r.status = "failed"
                    r.fallback_reason = f"批量提交失败: {str(exc)[:200]}"
                    r.error_type = type(exc).__name__
        else:
            db.rollback()

    rule_simple = sum(1 for r in results if r.status == "rule_simple")
    rule_template = sum(1 for r in results if r.status == "rule_template")
    llm_success = sum(1 for r in results if r.status == "llm_success")
    llm_fallback = sum(1 for r in results if r.status == "llm_fallback")
    failed = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")

    routed_llm = sum(1 for r in results if r.route == ComplexityRoute.LLM_REQUIRED.value)
    actual_llm = sum(1 for r in results if r.llm_called)
    est_saved = max(0, (len(results) - routed_llm)) * _EST_TOKENS_PER_LLM_CALL

    return BackfillReport(
        mode=mode,
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_selected=len(events),
        processed=len(results),
        rule_simple=rule_simple,
        rule_template=rule_template,
        llm_success=llm_success,
        llm_fallback=llm_fallback,
        failed=failed,
        skipped=skipped,
        estimated_full_llm_calls=len(results),
        estimated_routed_llm_calls=routed_llm,
        actual_llm_calls=actual_llm,
        estimated_tokens_saved=est_saved,
        duration_ms=int((time.perf_counter() - t_start) * 1000),
        results=results,
    )
