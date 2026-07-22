"""事件标题格式规则（聚合与叙事回填共用的单一事实来源）。

统一规则：多成员事件标题 = 『一条具体（非空）标题 + 等N条相关舆情聚集』。
  - 示例：「河北多举措推进基础教育扩优提质等2条相关舆情聚集」
  - 组合后超过 TITLE_SOFT_MAX(80) 时，将该具体标题用省略号截断：
    「河北多举措推进基础…等2条相关舆情聚集」
  - 全部标题为空时降级为不含风险等级的「共N条相关舆情聚集」
    （风险等级仍保留在描述中，不以「（risk风险）」形式出现在标题）。

本模块为纯函数、零 app 依赖，可被 aggregator 与 narrative 双向 import 而互不形成环。
"""
from __future__ import annotations

from typing import List, Sequence

# 标题软上限：与 narrative.check_narrative_quality 的 title_too_long(>80) 阈值对齐，
# 既保证人类可读，又避免触发质量红线。远低于 Event.title 列上限 String(512)。
TITLE_SOFT_MAX: int = 80


def representative_title(members: Sequence) -> str:
    """取一条具体（非空）标题作为代表；优先入参顺序中的首个非空标题。

    调用方负责按「时间升序」传入 members（Opinion 或 MemberFact 均可，只需有 .title），
    从而确保取到「最早一条非空标题」，与叙事回填的描述锚点一致、确定可复现。
    """
    for m in members:
        t = (getattr(m, "title", "") or "").strip()
        if t:
            return t
    return ""


def build_cluster_title(rep_title: str, count: int) -> str:
    """构造『具体标题 + 等N条相关舆情聚集』。

    - rep_title 为空（无可用标题）时降级为「共N条相关舆情聚集」；
    - 组合长度不超过 TITLE_SOFT_MAX；超出则截断具体标题并加省略号（…）。
    """
    n = count
    suffix = f"等{n}条相关舆情聚集"
    rep = (rep_title or "").strip()
    if not rep:
        return f"共{n}条相关舆情聚集"
    if len(rep) + len(suffix) <= TITLE_SOFT_MAX:
        return rep + suffix
    # 截断具体标题：预留 1 个省略号（…）与 suffix 长度
    budget = TITLE_SOFT_MAX - len(suffix) - 1
    if budget < 1:
        return suffix
    return rep[:budget] + "…" + suffix
