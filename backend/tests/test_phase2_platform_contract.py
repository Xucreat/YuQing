"""Phase 2 — 平台契约一致性测试（防漂移）。

验证四者永久一致：
  1. build_manifest() 生成的平台集合
  2. 运行 worker PLATFORMS 注册表（实际运行文件）
  3. 期望任务数量公式 3N+2
  4. 勘误版运行清单 phase1b_multikw_manifest.errata.json

运行：
  cd C:/Users/Administrator/Desktop/YQ/backend
  .venv/Scripts/python.exe -m pytest tests/test_phase2_platform_contract.py --noconftest -q

运行时间：2026-08-19
"""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

import pytest

from app.collectors.bb_browser_collector import (
    ALLOWED_PLATFORMS,
    HOT_PLATFORMS,
    PLATFORM_META,
    REJECTED_PLATFORMS,
    SEARCH_PLATFORMS,
    build_manifest,
    expected_tasks_for_manifest,
)

# 绝对路径（可由环境变量覆盖，便于 CI 复用）
WORKER_MAIN = os.environ.get(
    "BB_WORKER_MAIN",
    r"C:\Users\Administrator\Desktop\bb-browser 采集器\collector_exchange_runtime\collector_exchange\__main__.py",
)
ERRATA_JSON = os.environ.get(
    "BB_PHASE1B_ERRATA",
    r"C:\Users\Administrator\Desktop\bb-browser 采集器\phase1b_multikw_manifest.errata.json",
)

CANONICAL_SEARCH = ("baidu", "bilibili", "youtube")
CANONICAL_HOT = ("hupu", "toutiao")
# MediaCrawler 负责的、bb-browser 永不得接入的平台
NEVER_BB = {"weibo", "m_weibo", "xiaohongshu", "xhs", "zhihu"}


def _load_worker_platforms() -> dict:
    """从运行 worker 文件抽取 PLATFORMS 字典（仅字面量，安全 literal_eval）。"""
    path = Path(WORKER_MAIN)
    if not path.exists():
        pytest.skip(f"运行 worker 文件不存在：{WORKER_MAIN}（跳过，不报错）")
    text = path.read_text(encoding="utf-8", errors="ignore")
    idx = text.index("PLATFORMS = {")
    start = text.index("{", idx)
    depth = 0
    end = start
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return ast.literal_eval(text[start:end])


def test_collector_constants_match_canonical():
    assert tuple(SEARCH_PLATFORMS) == CANONICAL_SEARCH, "SEARCH_PLATFORMS 漂移"
    assert tuple(HOT_PLATFORMS) == CANONICAL_HOT, "HOT_PLATFORMS 漂移"
    assert "toutiao" not in SEARCH_PLATFORMS, "toutiao 不得是 search"
    assert "toutiao" in HOT_PLATFORMS, "toutiao 必须是 hot"
    assert tuple(ALLOWED_PLATFORMS) == (CANONICAL_SEARCH + CANONICAL_HOT)


def test_build_manifest_search_and_hot_split():
    text = build_manifest("m-test", ["河北", "廊坊", "北三县"], ALLOWED_PLATFORMS)
    search_in_manifest = set()
    hot_in_manifest = set()
    for block in re.findall(r"---BEGIN RULE---(.*?)---END RULE---", text, re.S):
        srcs = []
        kind = None
        for line in block.strip().splitlines():
            if line.startswith("sources="):
                srcs = [s.strip() for s in line.split("=", 1)[1].split(",") if s.strip()]
            if line.startswith("match_terms="):
                kind = "hot" if line.split("=", 1)[1].strip() == "__bb_browser_hot__" else "search"
        if kind == "search":
            search_in_manifest.update(srcs)
        else:
            hot_in_manifest.update(srcs)
    assert search_in_manifest == set(CANONICAL_SEARCH), f"manifest search 漂移: {search_in_manifest}"
    assert hot_in_manifest == set(CANONICAL_HOT), f"manifest hot 漂移: {hot_in_manifest}"
    assert "toutiao" not in search_in_manifest, "manifest 把 toutiao 误列 search"


def test_expected_task_count_formula():
    for n in (1, 2, 3, 5):
        text = build_manifest(f"m-{n}", ["k"] * n, ALLOWED_PLATFORMS)
        tasks = expected_tasks_for_manifest(text)
        assert len(tasks) == 3 * n + 2, f"N={n} 期望 3N+2={3*n+2}，实得 {len(tasks)}"
    # N=3 即 Phase 1B 验证所用
    text3 = build_manifest("m-3", ["河北", "廊坊", "北三县"], ALLOWED_PLATFORMS)
    assert len(expected_tasks_for_manifest(text3)) == 11


def test_worker_registry_kind_matches_collector():
    wp = _load_worker_platforms()
    for plat in ALLOWED_PLATFORMS:
        assert plat in wp, f"聚合平台 {plat} 不在运行 worker 注册表"
        assert wp[plat]["kind"] == PLATFORM_META[plat]["kind"], (
            f"kind 不一致：collector={PLATFORM_META[plat]['kind']} "
            f"worker={wp[plat]['kind']} (platform={plat})"
        )
    # toutiao 在 worker 注册表中必须是 hot
    assert wp["toutiao"]["kind"] == "hot"
    assert wp["baidu"]["kind"] == "search"
    assert wp["bilibili"]["kind"] == "search"
    assert wp["youtube"]["kind"] == "search"
    assert wp["hupu"]["kind"] == "hot"


def test_allowed_is_subset_of_worker_and_rejects_media_platforms():
    wp = _load_worker_platforms()
    for plat in ALLOWED_PLATFORMS:
        assert plat in wp
    # 任何 MediaCrawler / 排除平台都不得进入 bb-browser 聚合白名单
    for banned in NEVER_BB:
        assert banned not in ALLOWED_PLATFORMS, f"{banned} 不应出现在 ALLOWED_PLATFORMS"
    assert NEVER_BB.isdisjoint(set(ALLOWED_PLATFORMS))
    assert NEVER_BB.issuperset(set(REJECTED_PLATFORMS))


def test_errata_json_is_canonical_and_toutiao_not_search():
    path = Path(ERRATA_JSON)
    if not path.exists():
        pytest.skip(f"勘误清单不存在：{ERRATA_JSON}")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["search_platforms"] == list(CANONICAL_SEARCH), "勘误 search 漂移"
    assert data["hot_platforms"] == list(CANONICAL_HOT), "勘误 hot 漂移"
    assert "toutiao" not in data["search_platforms"], "勘误仍把 toutiao 列 search"
    assert data.get("toutiao_is_hot_not_search") is True
    # 排除平台必须显式记录
    excluded = data.get("excluded_platforms", {})
    for banned in ("weibo", "m_weibo", "xiaohongshu", "xhs", "zhihu"):
        assert banned in excluded, f"勘误缺少排除平台 {banned} 说明"
    # 期望任务总数仍为 11（3 关键词 × 3 + 2）
    assert data["expected_total"] == 11


def test_reverse_guard_toutiao_never_search():
    """反向守卫：若将来有人把 toutiao 误归 search，该测试必须失败。"""
    assert "toutiao" in HOT_PLATFORMS
    assert "toutiao" not in SEARCH_PLATFORMS
    assert HOT_PLATFORMS == CANONICAL_HOT
