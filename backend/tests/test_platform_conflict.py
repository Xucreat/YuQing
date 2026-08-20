"""平台冲突校验（bb-browser ↔ MediaCrawler）单元测试。

纯逻辑 + 轻量 fake DB（不连接真实测试库，pytest --noconftest 即可运行）。
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

import app.api.admin_data_sources as a
from app.collectors.platform_catalog import (
    PLATFORM_CATALOG,
    bb_browser_selectable_platforms,
    canonical_platform,
    compute_owned_platforms,
    dedupe_platforms,
    detect_platform_conflict,
)

BB = "app.collectors.bb_browser_collector.BBBrowserCollector"
MC_WB = "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector"
MC_XHS = "app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector"


# ---------------------------------------------------------------------------
# 目录 / 归一化基础
# ---------------------------------------------------------------------------
def test_catalog_stable_and_complete():
    keys = [p.key for p in PLATFORM_CATALOG]
    assert keys == ["baidu", "hupu", "toutiao", "bilibili", "youtube", "weibo", "xiaohongshu", "zhihu"]
    # bb-browser 可选 = Python 已完成归一化的平台（新增 xiaohongshu/zhihu）
    assert bb_browser_selectable_platforms() == {
        "baidu", "hupu", "toutiao", "bilibili", "youtube", "xiaohongshu", "zhihu",
    }


def test_canonical_alias():
    assert canonical_platform("m_weibo") == "weibo"
    assert canonical_platform("XHS") == "xiaohongshu"
    assert canonical_platform("Baidu") == "baidu"


def test_dedupe_preserves_order_and_normalizes():
    assert dedupe_platforms(["baidu", "baidu", "Baidu", "youtube"]) == ["baidu", "youtube"]
    assert dedupe_platforms(["weibo", "m_weibo"]) == ["weibo"]


# ---------------------------------------------------------------------------
# 平台占用计算（enabled 语义）
# ---------------------------------------------------------------------------
def test_owned_bb_enabled():
    assert compute_owned_platforms(BB, {"platforms": ["baidu", "weibo"]}, True) == {"baidu", "weibo"}


def test_owned_bb_disabled_returns_empty():
    # enabled=false 不占用任何平台（即使 config 里写了）
    assert compute_owned_platforms(BB, {"platforms": ["baidu", "weibo"]}, False) == set()


def test_owned_mc_enabled_uses_platform_field():
    assert compute_owned_platforms(MC_WB, {"platform": "weibo"}, True) == {"weibo"}


def test_owned_mc_disabled_returns_empty():
    assert compute_owned_platforms(MC_WB, {"platform": "weibo"}, False) == set()


def test_owned_generic_returns_empty():
    assert compute_owned_platforms("app.collectors.gov_site.GovernmentCollector", {}, True) == set()


# ---------------------------------------------------------------------------
# 冲突检测（六方向）
# ---------------------------------------------------------------------------
def test_bb_selecting_mc_weibo_conflicts():
    others = [(45, "微博（MediaCrawler）", MC_WB, True, {"platform": "weibo"})]
    c = detect_platform_conflict(BB, True, {"platforms": ["baidu", "weibo"]}, "bb-browser 聚合采集", others)
    assert c is not None
    assert "微博（MediaCrawler）" in c.message
    assert "bb-browser" in c.message


def test_mc_selecting_bb_weibo_conflicts():
    others = [(62, "bb-browser 聚合采集", BB, True, {"platforms": ["baidu", "weibo"]})]
    c = detect_platform_conflict(MC_WB, True, {"platform": "weibo"}, "微博（MediaCrawler）", others)
    assert c is not None
    assert "bb-browser 聚合采集" in c.message
    assert "MediaCrawler" in c.message


def test_mc_disabled_does_not_block_bb():
    others = [(45, "微博（MediaCrawler）", MC_WB, False, {"platform": "weibo"})]
    c = detect_platform_conflict(BB, True, {"platforms": ["baidu", "weibo"]}, "bb-browser 聚合采集", others)
    assert c is None


def test_mc_enabled_schedule_off_still_conflicts():
    # schedule_enabled 不影响占用判断，只看 enabled
    others = [(45, "微博（MediaCrawler）", MC_WB, True, {"platform": "weibo", "schedule_enabled": False})]
    c = detect_platform_conflict(BB, True, {"platforms": ["baidu", "weibo"]}, "bb-browser 聚合采集", others)
    assert c is not None


def test_bb_disabled_does_not_block_mc():
    others = [(62, "bb-browser 聚合采集", BB, False, {"platforms": ["weibo"]})]
    c = detect_platform_conflict(MC_WB, True, {"platform": "weibo"}, "微博（MediaCrawler）", others)
    assert c is None


def test_no_overlap_no_conflict():
    # bb 选百度，mc 选微博 -> 无交集
    others = [(45, "微博（MediaCrawler）", MC_WB, True, {"platform": "weibo"})]
    c = detect_platform_conflict(BB, True, {"platforms": ["baidu"]}, "bb-browser 聚合采集", others)
    assert c is None


def test_two_mc_same_platform_conflicts():
    others = [(45, "微博A（MediaCrawler）", MC_WB, True, {"platform": "weibo"})]
    c = detect_platform_conflict(MC_WB, True, {"platform": "weibo"}, "微博B（MediaCrawler）", others)
    assert c is not None


def test_two_bb_same_platform_conflicts():
    others = [(62, "bb-browser 1", BB, True, {"platforms": ["baidu", "hupu"]})]
    c = detect_platform_conflict(BB, True, {"platforms": ["baidu"]}, "bb-browser 2", others)
    assert c is not None


# ---------------------------------------------------------------------------
# 集成到 API helper（fake DB，不连真实库）
# ---------------------------------------------------------------------------
class _Row:
    def __init__(self, id, name, class_path, enabled, config_json):
        self.id = id
        self.name = name
        self.class_path = class_path
        self.enabled = enabled
        self.config_json = config_json


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Exec:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, stmt):
        return _Exec(self._rows)


def test_raise_if_conflict_409():
    # 已启用 MediaCrawler 微博；新建 bb-browser 也选微博 -> 409
    db = _FakeDB([
        _Row(45, "微博（MediaCrawler）", MC_WB, True, '{"platform": "weibo"}'),
    ])
    with pytest.raises(HTTPException) as ei:
        a._raise_if_platform_conflict(
            db, None, BB, True, {"platforms": ["baidu", "weibo"]}, "bb-browser 聚合采集"
        )
    assert ei.value.status_code == 409
    assert "微博" in ei.value.detail


def test_raise_if_no_conflict_passes():
    db = _FakeDB([
        _Row(45, "微博（MediaCrawler）", MC_WB, True, '{"platform": "weibo"}'),
    ])
    # bb 只选百度 -> 无冲突
    a._raise_if_platform_conflict(
        db, None, BB, True, {"platforms": ["baidu"]}, "bb-browser 聚合采集"
    )


def test_raise_if_other_disabled_passes():
    # 已禁用 MediaCrawler 微博 -> 不阻塞
    db = _FakeDB([
        _Row(45, "微博（MediaCrawler）", MC_WB, False, '{"platform": "weibo"}'),
    ])
    a._raise_if_platform_conflict(
        db, None, BB, True, {"platforms": ["baidu", "weibo"]}, "bb-browser 聚合采集"
    )


def test_raise_if_excludes_self():
    # 编辑自身时，_load_platform_owners(exclude_id=self_id) 会从 other_sources 中排除自身，
    # 因此自身已占用的平台不应与自身冲突。这里用纯函数模拟「排除自身后」的 others 为空。
    c = detect_platform_conflict(
        BB, True, {"platforms": ["baidu"]}, "bb-browser 聚合采集", []
    )
    assert c is None
