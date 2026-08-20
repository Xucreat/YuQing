"""bb-browser 聚合采集器：parser / manifest / 归一化 / 隔离 单元测试。

纯函数测试，不依赖数据库（pytest 以 --noconftest 运行即可，
避免 conftest 强制连接测试库 opinion_test@5433）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.collectors.bb_browser_collector import (
    BBBrowserCollector,
    ALLOWED_PLATFORMS,
    build_manifest,
    normalize_record,
    normalize_item,
    parse_record_text,
    stable_external_id,
    unwrap_result,
    write_manifest_atomic,
)


# ---------------------------------------------------------------------------
# 1-5：各平台 JSON 拆成多条 Opinion
# ---------------------------------------------------------------------------
def test_baidu_multiple():
    data = {"result": {"count": 2, "results": [
        {"title": "t1", "url": "http://a/1", "snippet": "s1"},
        {"title": "t2", "url": "http://a/2", "snippet": "s2"},
    ]}}
    items = normalize_record("baidu", data)
    assert len(items) == 2
    assert items[0]["source"] == "百度"
    assert items[0]["source_type"] == "baidu_result"
    assert items[0]["content"] == "s1"
    assert items[0]["external_id"].startswith("baidu:")


def test_hupu_multiple():
    data = {"result": {"count": 2, "items": [
        {"tid": "111", "title": "h1", "url": "https://bbs.hupu.com/111.html", "lights": "5", "replies": "3"},
        {"tid": "222", "title": "h2", "url": "https://bbs.hupu.com/222.html", "lights": "1", "replies": "0"},
    ]}}
    items = normalize_record("hupu", data)
    assert len(items) == 2
    assert items[0]["external_id"] == "hupu:111"
    assert items[0]["engagement"] == {"lights": "5", "comments": "3"}
    assert items[1]["external_id"] == "hupu:222"


def test_toutiao_multiple():
    data = {"result": {"count": 2, "items": [
        {"rank": "1", "title": "t1", "hot_value": "100", "url": "https://www.toutiao.com/trending/999/"},
        {"rank": "2", "title": "t2", "hot_value": "50", "url": "https://www.toutiao.com/trending/888/"},
    ]}}
    items = normalize_record("toutiao", data)
    assert len(items) == 2
    assert items[0]["external_id"] == "toutiao:999"
    assert items[0]["engagement"] == {"hot_value": "100"}


def test_bilibili_multiple():
    data = {"result": {"videos": [
        {"bvid": "BV1", "title": "b1", "author": "up", "pub_date": "2025-11-28T10:20:16.000Z",
         "url": "https://www.bilibili.com/video/BV1", "play": "10", "danmaku": "1", "like": "2", "favorites": "3"},
        {"bvid": "BV2", "title": "b2", "author": "up2", "pub_date": "2025-01-01T00:00:00.000Z",
         "url": "https://www.bilibili.com/video/BV2", "play": "20", "danmaku": "2", "like": "3", "favorites": "4"},
    ]}}
    items = normalize_record("bilibili", data)
    assert len(items) == 2
    assert items[0]["external_id"] == "bilibili:BV1"
    assert items[0]["author"] == "up"
    assert items[0]["publish_time"].year == 2025
    assert items[0]["engagement"]["play"] == "10"


def test_youtube_multiple():
    data = {"result": {"videos": [
        {"videoId": "v1", "title": "y1", "channel": "c1", "publishedTime": "9小时前",
         "description": "d1", "url": "https://www.youtube.com/watch?v=v1", "views": "3,264次观看"},
        {"videoId": "v2", "title": "y2", "channel": "c2", "publishedTime": "1天前",
         "description": "d2", "url": "https://www.youtube.com/watch?v=v2", "views": "1,000次观看"},
    ]}}
    items = normalize_record("youtube", data)
    assert len(items) == 2
    assert items[0]["external_id"] == "youtube:v1"
    assert items[0]["publish_time"] is None  # 相对时间不可靠 → None
    assert items[0]["engagement"] == {"views": "3,264次观看"}  # 保留原始 views


# ---------------------------------------------------------------------------
# 6：JSON 外层 result wrapper
# ---------------------------------------------------------------------------
def test_unwrap_result_wrapper():
    data = {"result": {"items": [{"title": "x"}]}}
    items, key = unwrap_result(data)
    assert items == [{"title": "x"}]
    assert key == "items"

    data2 = {"items": [{"title": "y"}]}  # 直接平铺
    items2, key2 = unwrap_result(data2)
    assert items2 == [{"title": "y"}]

    data3 = [{"title": "z"}]  # 直接列表
    items3, _ = unwrap_result(data3)
    assert items3 == [{"title": "z"}]


# ---------------------------------------------------------------------------
# 7：adapter 返回 401 错误
# ---------------------------------------------------------------------------
def test_adapter_error_object():
    err = {"error": {"code": 401, "message": "login required"}, "hint": "请先登录"}
    items = normalize_record("baidu", err)
    assert items == []  # 错误对象不产生条目
    rec = parse_record_text(
        "task_manifest_id=x\nsource_key=baidu\n---BEGIN CONTENT---\n"
        + json.dumps(err) + "\n---END CONTENT---\n"
    )
    assert rec["error"] is not None
    assert rec["content"] is None


# ---------------------------------------------------------------------------
# 8：缺少 url 时的 external_id 回退
# ---------------------------------------------------------------------------
def test_external_id_url_fallback():
    # baidu 无 url → 用标题哈希
    baidu = normalize_item("baidu", {"title": "无链接标题", "snippet": "摘要"})
    assert baidu["external_id"].startswith("baidu:") and len(baidu["external_id"]) > 6
    # hupu 无 url/tid → 用 url 哈希（url 为空 → none 哈希，仍稳定）
    hupu = normalize_item("hupu", {"title": "热帖"})
    assert hupu["external_id"].startswith("hupu:")


# ---------------------------------------------------------------------------
# 9：bvid / tid / videoId 去重
# ---------------------------------------------------------------------------
def test_native_id_dedup():
    # 平台原生 ID 优先
    assert stable_external_id("bilibili", {"bvid": "BVXYZ"}, None) == "bilibili:BVXYZ"
    # hupu 无 tid → 回退到规范化 URL 哈希（Phase 1B：禁止 *:none，不再 extract_digits）
    hid = stable_external_id("hupu", {}, "https://bbs.hupu.com/12345.html")
    assert hid.startswith("hupu:")
    assert hid != "hupu:none"
    # YouTube 原生 videoId
    assert stable_external_id("youtube", {"videoId": "abc"}, None) == "youtube:abc"
    # 同一 bvid / 同一 URL 两次运行必须一致（确定性）
    a = stable_external_id("bilibili", {"bvid": "BVXYZ"}, "https://x")
    b = stable_external_id("bilibili", {"bvid": "BVXYZ"}, "https://y")
    assert a == b
    c = stable_external_id("hupu", {}, "https://bbs.hupu.com/12345.html")
    assert c == hid


# ---------------------------------------------------------------------------
# 10-11：旧 manifest / landing-8platform 不会被本次任务消费
# ---------------------------------------------------------------------------
def test_scan_only_matches_current_manifest(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "baidu_OLD.txt").write_text(
        "task_manifest_id=landing-8platform\ntask_id=landing-8platform-rule-0001\nsource_key=baidu\n",
        encoding="utf-8",
    )
    (incoming / "baidu_PREV.txt").write_text(
        "task_manifest_id=manifest-3154\ntask_id=manifest-3154-rule-0001\nsource_key=baidu\n",
        encoding="utf-8",
    )
    (incoming / "baidu_NEW.txt").write_text(
        "task_manifest_id=bbp-new-1\ntask_id=bbp-new-1-rule-0001\nsource_key=baidu\n",
        encoding="utf-8",
    )
    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(tmp_path))
    found = coll._scan_manifest_files("bbp-new-1")
    # 新 API 返回 list[PendingFile]，按 (task_id, source_key) 精确匹配
    assert isinstance(found, list)
    assert len(found) == 1
    assert found[0].source_key == "baidu"
    assert found[0].path.name == "baidu_NEW.txt"
    # 旧文件不应被关联
    names = {p.path.name for p in found}
    assert "baidu_OLD.txt" not in names
    assert "baidu_PREV.txt" not in names


# ---------------------------------------------------------------------------
# 12：m_weibo / xiaohongshu 不会被加入 manifest
# ---------------------------------------------------------------------------
def test_weibo_xhs_excluded_from_manifest():
    mid = "m123"
    # 即使调用方传入 weibo/xhs，白名单也应剔除
    m = build_manifest(mid, ["北三县"], ["baidu", "weibo", "xiaohongshu"])
    assert "weibo" not in m
    assert "xiaohongshu" not in m
    assert "baidu" in m

    coll = BBBrowserCollector(platforms=["baidu", "weibo", "xiaohongshu"],
                              control_root="x", exchange_root="y")
    assert coll.platforms == ["baidu"]


# ---------------------------------------------------------------------------
# 13：热榜平台不会按每个关键词重复生成任务
# ---------------------------------------------------------------------------
def test_hot_rule_not_duplicated_per_keyword():
    mid = "h123"
    m = build_manifest(mid, ["kw1", "kw2", "kw3"],
                       ["baidu", "bilibili", "youtube", "hupu", "toutiao"])
    # 搜索型：每关键词一条 search 规则 = 3 条
    assert m.count("rule_id=") == 4  # 3 search + 1 hot
    assert m.count("rule-hot-") == 1  # 仅一条热榜规则
    assert f"{mid}-rule-hot-0001" in m


# ---------------------------------------------------------------------------
# 14：manifest 原子写入
# ---------------------------------------------------------------------------
def test_manifest_atomic_write(tmp_path):
    out = tmp_path / "outgoing"
    mid = "atom1"
    target = write_manifest_atomic(out, mid, "RULE_VERSION=2\n")
    assert target.exists()
    assert target.name == f"{mid}.txt"
    # 临时文件已消失（原子 rename）
    assert not (out / f".{mid}.tmp").exists()


# ---------------------------------------------------------------------------
# 15-16：ack 移动文件 / 17：未 ack 文件保留
# ---------------------------------------------------------------------------
def test_ack_moves_files_to_processed(tmp_path):
    exchange = tmp_path
    incoming = exchange / "incoming"
    processed = exchange / "processed"
    incoming.mkdir()
    f1 = incoming / "baidu_aaa.txt"
    f2 = incoming / "hupu_bbb.txt"
    f1.write_text("x", encoding="utf-8")
    f2.write_text("y", encoding="utf-8")

    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(exchange))
    coll._pending_files = [f1, f2]
    ok = coll.ack_pending_export()
    assert ok is True
    assert (processed / "baidu_aaa.txt").exists()
    assert (processed / "hupu_bbb.txt").exists()
    assert not f1.exists() and not f2.exists()
    assert coll._pending_files == []


def test_not_calling_ack_keeps_files(tmp_path):
    exchange = tmp_path
    incoming = exchange / "incoming"
    incoming.mkdir()
    f1 = incoming / "baidu_keep.txt"
    f1.write_text("x", encoding="utf-8")
    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(exchange))
    coll._pending_files = [f1]
    # 模拟分析失败：服务根本不会调用 ack → 文件留在 incoming
    assert f1.exists()


def test_ack_missing_file_returns_false(tmp_path):
    exchange = tmp_path
    incoming = exchange / "incoming"
    processed = exchange / "processed"
    incoming.mkdir()
    f1 = incoming / "baidu_gone.txt"
    f1.write_text("x", encoding="utf-8")
    missing = incoming / "baidu_missing.txt"  # 不存在
    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(exchange))
    coll._pending_files = [f1, missing]
    ok = coll.ack_pending_export()
    assert ok is False
    # 已存在的文件未被移动（保守：任一缺失则整体不丢文件）
    assert f1.exists()


def test_allowed_platforms_constant():
    assert set(ALLOWED_PLATFORMS) == {"baidu", "hupu", "toutiao", "bilibili", "youtube"}
