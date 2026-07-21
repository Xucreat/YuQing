"""舆情基础 CRUD API（Phase 2A）。

路由（均挂载在 /api 下，由 main.py 统一加前缀）：
  GET    /opinions          列表（分页 + source/risk_level/keyword 过滤）
  GET    /opinions/{id}     详情（404: "Opinion not found"）
  POST   /opinions          创建（供未来 Collector 写入；默认 risk_score=0 / sentiment=neutral）
  DELETE /opinions/{id}     删除（MVP 保留）

所有路由受 Depends(get_current_user) 保护（Bearer JWT）。
禁止提前实现：AI Service / DeepSeek / Collector / Event 聚合 / Dashboard。
"""
from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, delete as sa_delete, text
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.opinion import Opinion
from app.models.user import User
from app.models.region import Region
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRecord
from app.schemas.opinion import OpinionCreate, OpinionListResponse, OpinionOut

opinions_router = APIRouter(
    tags=["opinions"],
    # 全部舆情接口均需登录（Bearer JWT）
    dependencies=[Depends(get_current_user)],
)

MAX_SIZE = 100


@opinions_router.get("", response_model=OpinionListResponse)
def list_opinions(
    page: int = 1,
    size: int = 20,
    q: str | None = None,
    source: str | None = None,
    risk_level: str | None = None,
    risk_min: int | None = None,
    risk_max: int | None = None,
    keyword: str | None = None,
    sentiment: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
) -> OpinionListResponse:
    """分页列表，支持来源 / 风险等级 / 关键词 / 发布日期过滤。

    risk_level 映射到 opinions.sentiment（positive|negative|neutral，
    因 opinions 表无 risk_level 列，按用户约束不改动数据库结构）。
    keyword 对 keywords / title / content 做模糊匹配。
    date_from / date_to 为 YYYY-MM-DD 字符串，按 publish_time 的日期部分过滤。
    """
    page = max(page, 1)
    size = max(min(size, MAX_SIZE), 1)

    stmt = select(Opinion)
    # P1: full-text search using PostgreSQL ts_vector
    if q:
        tsq = func.plainto_tsquery("simple", q)
        stmt = stmt.where(func.coalesce(Opinion.search_vector, text("''::tsvector")).op("@@")(tsq))
    if source:
        stmt = stmt.where(Opinion.source == source)
    if risk_level:
        stmt = stmt.where(Opinion.sentiment == risk_level)
    if risk_min is not None:
        stmt = stmt.where(Opinion.risk_score >= risk_min)
    if risk_max is not None:
        stmt = stmt.where(Opinion.risk_score <= risk_max)
    if sentiment:
        stmt = stmt.where(Opinion.sentiment == sentiment)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                Opinion.keywords.ilike(like),
                Opinion.title.ilike(like),
                Opinion.content.ilike(like),
            )
        )
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d").date()
            stmt = stmt.where(func.date(Opinion.publish_time) >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d").date()
            stmt = stmt.where(func.date(Opinion.publish_time) <= d)
        except ValueError:
            pass

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Opinion.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    return OpinionListResponse(items=rows, total=total, page=page, size=size)


@opinions_router.get("/sources", response_model=list[str])
def list_opinion_sources(db: Session = Depends(get_db)) -> list[str]:
    """返回库中全部去重且非空的来源名称（按舆情数量降序）。

    供前端「来源」筛选项下拉使用，避免仅按当前页数据聚合导致选项不全。
    """
    rows = db.execute(
        select(Opinion.source)
        .where(Opinion.source != "")
        .group_by(Opinion.source)
        .order_by(func.count(Opinion.id).desc())
    ).all()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# 实时抓取来源页原文（详情弹窗展示比标题更长的原文）
# ---------------------------------------------------------------------------
_ORIGINAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
# 进程内简单缓存，避免同一 url 重复抓取（重启丢失，演示足够）
_ORIGINAL_CACHE: dict[str, list[str]] = {}


class _TextCollector(HTMLParser):
    """轻量 HTML 正文抽取：跳过脚本/样式/导航，按块收集可见文本。"""

    _SKIP_TAGS = {"script", "style", "head", "noscript", "header", "footer", "nav", "aside", "iframe", "svg"}
    _BLOCK_TAGS = {"p", "div", "section", "article", "li"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._buf: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip += 1
        if tag in self._BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        if tag in self._BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        if self._skip:
            return
        t = data.strip()
        if t:
            self._buf.append(t)

    def _flush(self):
        if self._buf:
            text = "".join(self._buf).strip()
            if text:
                self.paragraphs.append(text)
            self._buf = []


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _is_sentence(text: str) -> bool:
    """是否像正文句子：含句末标点，或较长且含句中标点。导航/菜单碎片通常无标点。"""
    if re.search(r"[。！？]", text):
        return True
    return len(text) >= 40 and bool(re.search(r"[，、；：]", text))


_NOISE_RE = re.compile(
    r"(举报|版权所有|copyright|©|all rights reserved|联系我们|邮箱|电话|"
    r"备案|京icp|公网安备|隐私政策|关于我们|网站地图|"
    r"关注我们|扫码|分享到|点击查看|登录|注册|免责声明)"
)


def _is_noise(text: str) -> bool:
    """导航条 / 页脚 / 版权等噪声块。"""
    low = text.lower()
    if _NOISE_RE.search(low):
        return True
    # 纯英文或纯数字串（统计代码、邮箱、跳转文案）通常不是中文正文
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    if len(text) > 6 and cjk == 0:
        return True
    return False


def _extract_meta_description(html: str) -> str:
    """JS 渲染站点静态 HTML 无正文时，退而取 og:description / description。"""
    for tag in re.findall(r"<meta\b[^>]*>", html, re.I):
        low = tag.lower()
        if "og:description" in low or 'name="description"' in low or "name='description'" in low:
            m = re.search(r'content=["\']([^"\']+)["\']', tag, re.I)
            if m:
                return m.group(1).strip()
    return ""


def _extract_paragraphs(html: str, max_paras: int = 8, max_chars: int = 1600) -> list[str]:
    """从 HTML 抽取正文段落。

    策略：优先保留「带句末标点」的正文句子（导航/菜单碎片通常无标点），
    过滤极短 / 无中文 / 重复噪声；不足时回退 og:description。
    """
    collector = _TextCollector()
    try:
        collector.feed(html)
    except Exception:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for para in collector.paragraphs:
        c = re.sub(r"\s+", " ", para).strip()
        if len(c) < 25 or not _has_cjk(c) or c in seen or _is_noise(c):
            continue
        seen.add(c)
        cleaned.append(c)
    if not cleaned:
        return []

    # 优先取像正文的句子（含句末标点）；没有则退回全部候选
    sentences = [c for c in cleaned if _is_sentence(c)]
    pool = sentences if sentences else cleaned
    longest = set(sorted(pool, key=len, reverse=True)[:max_paras])
    ordered = [c for c in pool if c in longest][:max_paras]
    out: list[str] = []
    total = 0
    for c in ordered:
        if total + len(c) > max_chars:
            break
        out.append(c)
        total += len(c)
    if not out:
        meta = _extract_meta_description(html)
        if len(meta) >= 25 and _has_cjk(meta):
            out = [meta]
    return out


@opinions_router.get("/{opinion_id}/original")
def get_opinion_original(opinion_id: int, db: Session = Depends(get_db)):
    """实时抓取来源页并抽取正文段落，供详情弹窗展示比标题更长的原文。

    抓取失败 / 无 url / 无正文时 original 为空，前端回退到 opinion.content。
    """
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opinion not found",
        )
    url = (opinion.url or "").strip()
    fallback = opinion.content or ""
    if not url:
        return {"url": None, "original": [], "fallback": fallback, "fetched": False}
    if url in _ORIGINAL_CACHE:
        return {"url": url, "original": _ORIGINAL_CACHE[url], "fallback": fallback, "fetched": True}
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": _ORIGINAL_UA})
        resp.encoding = resp.apparent_encoding or "utf-8"
        paras = _extract_paragraphs(resp.text)
    except Exception:
        paras = []
    _ORIGINAL_CACHE[url] = paras
    return {"url": url, "original": paras, "fallback": fallback, "fetched": bool(paras)}


@opinions_router.get("/{opinion_id}", response_model=OpinionOut)
def get_opinion(opinion_id: int, db: Session = Depends(get_db)) -> Opinion:
    """舆情详情；不存在返回 404 {"detail":"Opinion not found"}。"""
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opinion not found",
        )
    return opinion


@opinions_router.post("", response_model=OpinionOut, status_code=status.HTTP_201_CREATED)
def create_opinion(
    payload: OpinionCreate,
    _: User = Depends(require_permission("opinions:write")),
    db: Session = Depends(get_db),
) -> Opinion:
    """创建舆情（供未来 Collector 写入）。

    创建后默认 risk_score=0、sentiment="neutral"（AI 阶段再更新）。
    region_id 必须存在，否则 404 "Region not found"。
    """
    region = db.get(Region, payload.region_id)
    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )

    opinion = Opinion(
        title=payload.title,
        content=payload.content,
        source=payload.source,
        url=payload.url,
        publish_time=payload.publish_time,
        region_id=payload.region_id,
        risk_score=0,
        sentiment="neutral",
    )
    db.add(opinion)
    db.commit()
    db.refresh(opinion)
    return opinion


@opinions_router.delete("/{opinion_id}", status_code=status.HTTP_200_OK)
def delete_opinion(
    opinion_id: int,
    _: User = Depends(require_permission("opinions:write")),
    db: Session = Depends(get_db),
) -> dict:
    """Delete opinion with cascade cleanup of related records."""
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opinion not found",
        )

    # Cascade-clean related records before deleting opinion
    from app.models.propagation import PropagationNode
    for eo in db.query(EventOpinion).where(EventOpinion.opinion_id == opinion_id).all():
        db.delete(eo)
    db.query(AlertRecord).where(AlertRecord.opinion_id == opinion_id).update(
        {"opinion_id": None}, synchronize_session=False
    )
    # Nullify parent references first to avoid FK violations when
    # other nodes still point to the ones being deleted.
    nodes = db.query(PropagationNode).where(PropagationNode.opinion_id == opinion_id).all()
    if nodes:
        node_ids = [n.id for n in nodes]
        db.query(PropagationNode).where(
            PropagationNode.parent_id.in_(node_ids)
        ).update({"parent_id": None}, synchronize_session=False)
        for pn in nodes:
            db.delete(pn)
    db.flush()
    db.delete(opinion)
    db.commit()
    return {"detail": "Opinion deleted", "id": opinion_id}