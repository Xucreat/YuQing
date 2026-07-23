"""初始化数据脚本（种子数据）。

用法（在 backend/ 目录下执行）：
    python scripts/init_db.py

前置：先执行 `alembic upgrade head` 创建表结构。
本脚本写入种子数据（幂等，insert-if-missing，不覆盖手动调整）：
    - 管理员 admin / admin123（bcrypt 加密，禁止明文）
    - 区域：河北省(130000) → 11 地级市 → 雄安新区(133100) → 关键县（大厂/三河/香河/固安）
    - 数据源 data_sources：
        · 既有 9 个真实源（与迁移前行为一致，class_path 指向原 bespoke 采集器）
        · 市级/县级政府网（GenericSiteCollector 配置行，无新 .py 文件）

说明：脚本开头调用 Base.metadata.create_all 作为安全网，
      即使未执行 Alembic 也能建表；与 Alembic 共存无冲突。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保 backend/ 在 sys.path，便于直接运行脚本
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
import app.models  # noqa: F401  注册模型
from app.models.user import User
from app.models.region import Region
from app.models.keyword import Keyword
from app.models.data_source import DataSource


# ---------------------------------------------------------------------------
# 区域种子：河北省 → 11 地级市 → 雄安新区 → 关键县（省→市→县树）
# (code, name, level, parent_code)
# ---------------------------------------------------------------------------
REGION_SEED: list = [
    ("130000", "河北省", "province", None),
    # 11 地级市
    ("130100", "石家庄市", "city", "130000"),
    ("130200", "唐山市", "city", "130000"),
    ("130300", "秦皇岛市", "city", "130000"),
    ("130400", "邯郸市", "city", "130000"),
    ("130500", "邢台市", "city", "130000"),
    ("130600", "保定市", "city", "130000"),
    ("130700", "张家口市", "city", "130000"),
    ("130800", "承德市", "city", "130000"),
    ("130900", "沧州市", "city", "130000"),
    ("131000", "廊坊市", "city", "130000"),
    ("131100", "衡水市", "city", "130000"),
    # 雄安新区（省级直管，归省下）
    ("133100", "雄安新区", "city", "130000"),
    # 关键县（廊坊市下）
    ("131028", "大厂回族自治县", "county", "131000"),
    ("131082", "三河市", "county", "131000"),
    ("131024", "香河县", "county", "131000"),
    ("131022", "固安县", "county", "131000"),
]


# ---------------------------------------------------------------------------
# 既有 9 个真实数据源（迁移前行为，class_path 指向原 bespoke 采集器）。
# 与 collectors/registry.py 的 DEFAULT_SOURCES 保持一致，保证零回归。
# ---------------------------------------------------------------------------
EXISTING_SOURCES: list = [
    {
        "key": "government", "name": "大厂县政府网站", "type": "gov_site",
        "class_path": "app.collectors.government_collector.GovernmentCollector",
        "enabled": True, "priority": 10, "scope_region_codes": "131028",
        "config_json": "{}",
    },
    {
        "key": "baidu_news", "name": "百度新闻", "type": "search",
        "class_path": "app.collectors.baidu_news_collector.BaiduNewsCollector",
        "enabled": True, "priority": 20, "scope_region_codes": "",
        "config_json": "{}",
    },
    {
        "key": "hebei_news", "name": "河北新闻网", "type": "news_site",
        "class_path": "app.collectors.hebei_news_collector.HebeiNewsCollector",
        "enabled": True, "priority": 30, "scope_region_codes": "130000",
        "config_json": "{}",
    },
    {
        "key": "xinhua", "name": "新华网", "type": "news_site",
        "class_path": "app.collectors.xinhua_collector.XinhuaCollector",
        "enabled": True, "priority": 40, "scope_region_codes": "",
        "config_json": "{}",
    },
    {
        "key": "people", "name": "人民网", "type": "news_site",
        "class_path": "app.collectors.people_collector.PeopleCollector",
        "enabled": True, "priority": 50, "scope_region_codes": "",
        "config_json": "{}",
    },
    {
        "key": "chinanews", "name": "中国新闻网", "type": "rss",
        "class_path": "app.collectors.chinanews_collector.ChinanewsCollector",
        "enabled": True, "priority": 55, "scope_region_codes": "",
        "config_json": "{}",
    },
    {
        "key": "hebei_daily", "name": "河北日报", "type": "news_site",
        "class_path": "app.collectors.hebei_daily_collector.HebeiDailyCollector",
        "enabled": True, "priority": 60, "scope_region_codes": "130000",
        "config_json": "{}",
    },
    {
        "key": "changcheng", "name": "长城网", "type": "news_site",
        "class_path": "app.collectors.changcheng_collector.ChangchengCollector",
        "enabled": True, "priority": 65, "scope_region_codes": "130000",
        "config_json": "{}",
    },
    {
        "key": "hebei_gov", "name": "河北省人民政府", "type": "gov_site",
        "class_path": "app.collectors.hebei_gov_collector.HebeiGovCollector",
        "enabled": True, "priority": 70, "scope_region_codes": "130000",
        "config_json": "{}",
    },
]


# ---------------------------------------------------------------------------
# 市级 / 县级政府网（GenericSiteCollector 配置行；探测结果回填）。
# 每项：key, name, scope_region_codes, config_dict（→ config_json）
# 注意：list_urls / content_selectors / keywords 来自 scripts/probe_cities.py 探测。
# ---------------------------------------------------------------------------
# 探测结果（scripts/probe_cities.py / probe_extra.py）回填。
# enabled=True 的为「已验证可抓取」；enabled=False 为「已配置但当前网络/反爬不可达，
# 灰度保留，后续网络通畅或找到列表页后翻转 enabled 即可激活，无需改代码」。
CITY_CONFIGS: dict = {
    # —— 已验证可抓取（7 个，满足 ≥5 市级源实际抓取）——
    "shijiazhuang_gov": {"name": "石家庄市政府网", "scope": "130100", "priority": 100,
        "config": {"list_urls": ["http://www.sjz.gov.cn/zfxxgk/columns/e7de71c2-8e82-4a75-8c37-02e1a3ae5a24/index.html"],
                   "keywords": "石家庄,河北", "content_selectors": ["div.nr"]}},
    "handan_gov": {"name": "邯郸市政府网", "scope": "130400", "priority": 105,
        "config": {"list_urls": ["http://www.hd.gov.cn/qt/hdxw/201804/t20180421_778773.html"],
                   "keywords": "邯郸,河北", "content_selectors": ["div.TRS_Editor"]}},
    "baoding_gov": {"name": "保定市政府网", "scope": "130600", "priority": 110,
        "config": {"list_urls": ["http://www.baoding.gov.cn/content-159-539629.html"],
                   "keywords": "保定,河北", "content_selectors": ["div.sj_nrbr"]}},
    "zhangjiakou_gov": {"name": "张家口市政府网", "scope": "130700", "priority": 115,
        "config": {"list_urls": ["https://www.zjk.gov.cn/channel/list/14.html"],
                   "keywords": "张家口,河北", "content_selectors": ["div.content"]}},
    "chengde_gov": {"name": "承德市政府网", "scope": "130800", "priority": 120,
        "config": {"list_urls": ["http://www.chengde.gov.cn/col/col9943/index.html?number=CD0004A00006"],
                   "keywords": "承德,河北", "content_selectors": ["div.content"]}},
    "hengshui_gov": {"name": "衡水市政府网", "scope": "131100", "priority": 125,
        "config": {"list_urls": ["http://www.hengshui.gov.cn/col/col45/index.html"],
                   "keywords": "衡水,河北", "content_selectors": ["div.neirong"]}},
    "xiongan_gov": {"name": "雄安新区管委会", "scope": "133100", "priority": 130,
        "config": {"list_urls": ["http://www.xiongan.gov.cn/tzgg.html"],
                   "keywords": "雄安,河北", "content_selectors": ["div.text"]}},

    # —— Phase 3b：受限市/县的「替代新闻源」（日报/新闻网/融媒，已实测可抓取，enabled=True）——
    # 说明：政务网被反爬/宕机时，改用当地日报/新闻网。scope 仍绑定对应地市 code。
    "tangshan_huanbohai": {"name": "唐山环渤海新闻网", "scope": "130200", "priority": 136,
        "config": {"list_urls": ["http://tangshan.huanbohainews.com.cn/node_223.html",
                                  "http://tangshan.huanbohainews.com.cn/node_824.html",
                                  "http://tangshan.huanbohainews.com.cn/"],
                   "keywords": "", "content_selectors": ["div.content", "div.article", "div.TRS_Editor"],
                   "link_rule": {"href_contains": "content_", "min_title_len": 0, "max_links": 40}}},
    "qinhuangdao_news": {"name": "秦皇岛新闻网", "scope": "130300", "priority": 141,
        "config": {"list_urls": ["http://www.qhdnews.com/"],
                   "keywords": "", "content_selectors": ["div.content", "div.article", "div.TRS_Editor", "div.text"],
                   "link_rule": {"href_contains": "/content/", "max_links": 40}}},
    "xingtai_daily": {"name": "邢台网(邢台日报)", "scope": "130500", "priority": 146,
        "config": {"list_urls": ["http://www.xtrb.cn/"],
                   "keywords": "", "content_selectors": ["div.content", "div.article", "div.TRS_Editor"],
                   "link_rule": {"href_contains": "/xt/", "href_exclude": ["speDetail"], "max_links": 40}}},
    "cangzhou_news": {"name": "沧州新闻(河北新闻网沧州频道)", "scope": "130900", "priority": 151,
        "config": {"list_urls": ["http://cangzhou.hebnews.cn/"],
                   "keywords": "", "content_selectors": ["div.content", "div.article", "div.TRS_Editor"],
                   "link_rule": {"href_contains": "content_", "max_links": 40}}},
    "langfang_news": {"name": "廊坊新闻网", "scope": "131000", "priority": 156,
        "config": {"list_urls": ["http://www.lfnews.cn/"],
                   "keywords": "", "content_selectors": ["div.content", "td.article", "div.article", "div.message"],
                   "link_rule": {"href_contains": "mod=view", "href_exclude": ["mod=list"], "min_title_len": 6, "max_links": 40}}},
    "xianghe_news": {"name": "香河县政府网(新闻)", "scope": "131024", "priority": 166,
        "config": {"list_urls": ["http://www.xianghe.gov.cn/"],
                   "keywords": "香河,廊坊", "content_selectors": ["div.content", "div.article", "div.TRS_UEDITOR"],
                   "link_rule": {"href_contains": "/system/", "max_links": 40}}},

    # —— 原受限政务网：已被上方替代源接管，保留配置但 enabled=False（灰度，可回切）——
    "tangshan_gov": {"name": "唐山市政府网", "scope": "130200", "priority": 135, "enabled": False,
        "config": {"list_urls": ["http://www.tangshan.gov.cn"], "keywords": "唐山,河北"}},
    "qinhuangdao_gov": {"name": "秦皇岛市政府网", "scope": "130300", "priority": 140, "enabled": False,
        "config": {"list_urls": ["http://www.qhd.gov.cn"], "keywords": "秦皇岛,河北"}},
    "xingtai_gov": {"name": "邢台市政府网", "scope": "130500", "priority": 145, "enabled": False,
        "config": {"list_urls": ["http://www.xingtai.gov.cn"], "keywords": "邢台,河北"}},
    "cangzhou_gov": {"name": "沧州市政府网", "scope": "130900", "priority": 150, "enabled": False,
        "config": {"list_urls": ["http://www.cangzhou.gov.cn"], "keywords": "沧州,河北"}},
    "langfang_gov": {"name": "廊坊市政府网", "scope": "131000", "priority": 155, "enabled": False,
        "config": {"list_urls": ["http://www.lf.gov.cn"], "keywords": "廊坊,河北"}},
    "xianghe_gov": {"name": "香河县政府网", "scope": "131024", "priority": 165, "enabled": False,
        "config": {"list_urls": ["http://www.xianghe.gov.cn"], "keywords": "香河,廊坊,河北"}},
    # —— 县级：当前网络/反爬受限，无可用替代源，enabled=False，保留配置待激活 ——
    "sanhe_gov": {"name": "三河市政府网", "scope": "131082", "priority": 160, "enabled": False,
        "config": {"list_urls": ["http://www.sanhe.gov.cn"], "keywords": "三河,廊坊,河北"}},
    "guan_gov": {"name": "固安县政府网", "scope": "131022", "priority": 170, "enabled": False,
        "config": {"list_urls": ["http://www.guanan.gov.cn"], "keywords": "固安,廊坊,河北"}},
}


def _generic_config(source_name: str, list_urls, scope: str,
                     keywords: str | None = None,
                     content_selectors: list | None = None,
                     max_articles: int = 8,
                     link_rule: dict | None = None) -> str:
    cfg: dict = {
        "source_name": source_name,
        "list_urls": list_urls,
        "max_articles": max_articles,
    }
    # keywords 允许显式空串（""=放行全部，用于天然区域绑定的市/县报）
    if keywords is not None:
        cfg["keywords"] = keywords
    if content_selectors:
        cfg["content_selectors"] = content_selectors
    if link_rule:
        cfg["link_rule"] = link_rule
    return json.dumps(cfg, ensure_ascii=False)


# 默认敏感词种子（仅数据，不改表结构）。
DEFAULT_KEYWORDS = [
    ("火灾", 8, "安全事故"),
    ("爆炸", 9, "安全事故"),
    ("事故", 6, "安全事故"),
    ("伤亡", 9, "安全事故"),
    ("死亡", 8, "安全事故"),
    ("冲突", 7, "社会稳定"),
    ("群体", 7, "社会稳定"),
    ("上访", 8, "社会稳定"),
    ("维权", 6, "社会稳定"),
    ("投诉", 4, "民生服务"),
    ("谣言", 8, "网络舆情"),
    ("诈骗", 8, "违法犯罪"),
    ("腐败", 7, "廉政风险"),
    ("贪污", 7, "廉政风险"),
    ("涉警", 8, "涉警舆情"),
    ("舆情", 3, "网络舆情"),
]


# 默认监测关键词种子（keywords 表 = 采集过滤 + 预警匹配的唯一权威源）。
# 覆盖河北省全域（省 + 11 地级市 + 雄安 + 重点县）+ 常见舆情主题。
MONITORING_KEYWORD_SEED = [
    # —— 地域锚点（全省监测）——
    ("河北", 5, "地域"),
    ("石家庄", 5, "地域"),
    ("唐山", 4, "地域"),
    ("保定", 4, "地域"),
    ("邯郸", 4, "地域"),
    ("秦皇岛", 4, "地域"),
    ("邢台", 4, "地域"),
    ("沧州", 4, "地域"),
    ("衡水", 4, "地域"),
    ("张家口", 4, "地域"),
    ("承德", 4, "地域"),
    ("廊坊", 5, "地域"),
    ("雄安", 4, "地域"),
    ("大厂", 6, "地域"),
    ("大厂回族自治县", 5, "地域"),
    # —— 主题词 ——
    ("消防", 6, "主题"),
    ("安全生产", 6, "主题"),
    ("安全事故", 5, "主题"),
    ("民生", 5, "主题"),
    ("投诉", 4, "主题"),
    ("环保", 4, "主题"),
    ("征地", 4, "主题"),
    ("拆迁", 4, "主题"),
    ("食品安全", 4, "主题"),
    ("教育", 3, "主题"),
    ("医疗", 3, "主题"),
    ("交通", 3, "主题"),
    ("城管", 3, "主题"),
    ("舆情", 3, "主题"),
]


def _seed_keywords(db) -> None:
    """以监测关键词初始化 keywords 表（采集过滤 + 预警匹配唯一权威源）。

    - 表为空 → 直接播种 MONITORING_KEYWORD_SEED；
    - 表仅含旧版误播敏感词（历史 DEFAULT_KEYWORDS 子集）→ 清空重置；
    - 表已有用户维护的监测词 → 仅补齐缺失项，不破坏既有数据。
    """
    existing = db.query(Keyword.word).all()
    existing_words = {r[0] for r in existing}
    legacy = {w for w, _, _ in DEFAULT_KEYWORDS}
    if existing_words and existing_words.issubset(legacy):
        # 全是历史误播的敏感词 → 重置为监测词
        db.query(Keyword).delete()
        db.commit()
        existing_words = set()
        print("[init_db] 检测到 keywords 表仅含历史敏感词种子，已重置为监测词")

    if not existing_words:
        for word, weight, category in MONITORING_KEYWORD_SEED:
            if db.query(Keyword).filter(Keyword.word == word).first() is None:
                db.add(Keyword(word=word, weight=weight, category=category))
                print(f"[init_db] 已插入监测词: {word} (weight={weight})")
        db.commit()
    else:
        # 补齐缺失的监测词（不删除用户已有词）
        added = 0
        for word, weight, category in MONITORING_KEYWORD_SEED:
            if word not in existing_words and db.query(Keyword).filter(Keyword.word == word).first() is None:
                db.add(Keyword(word=word, weight=weight, category=category))
                added += 1
        if added:
            db.commit()
        print("[init_db] keywords 表已存在监测词，仅补齐缺失项")


def _seed_sensitive_keywords(db) -> None:
    """幂等播种系统内置敏感/风险词（type='sensitive', source='system'）。

    与监测词共享 keywords 表但 type 不同；首次运行写入，重复执行跳过已存在项。
    这些词用于风险评分（RuleFallbackProvider），受保护：可查看/筛选/启停，不可删除。
    """
    added = 0
    now = datetime.now(timezone.utc)
    for word, weight, category in DEFAULT_KEYWORDS:
        exists = (
            db.query(Keyword)
            .filter(Keyword.word == word, Keyword.type == "sensitive")
            .first()
        )
        if exists:
            continue
        db.add(
            Keyword(
                word=word,
                weight=weight,
                category=category,
                type="sensitive",
                source="system",
                is_enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        added += 1
    if added:
        db.commit()
        print(f"[init_db] 已播种系统敏感词 {added} 条")
    else:
        print("[init_db] 系统敏感词已存在，跳过")


def _seed_regions(db) -> None:
    for code, name, level, parent in REGION_SEED:
        if db.query(Region).filter(Region.code == code).first() is None:
            db.add(Region(code=code, name=name, level=level, parent_code=parent))
            print(f"[init_db] 已插入区域: {name} ({code}, {level})")
        else:
            print(f"[init_db] 区域已存在，跳过: {name}")


def _seed_data_sources(db) -> None:
    # 1) 既有 9 源（零回归）
    for s in EXISTING_SOURCES:
        if db.query(DataSource).filter(DataSource.key == s["key"]).first() is None:
            db.add(DataSource(
                key=s["key"], name=s["name"], type=s["type"],
                class_path=s["class_path"], enabled=s["enabled"],
                priority=s["priority"], scope_region_codes=s.get("scope_region_codes") or None,
                config_json=s.get("config_json"),
            ))
            print(f"[init_db] 已插入数据源: {s['name']} ({s['key']})")
        else:
            print(f"[init_db] 数据源已存在，跳过: {s['key']}")

    # 2) 市级/县级政府网（GenericSiteCollector 配置行）
    for key, spec in CITY_CONFIGS.items():
        if db.query(DataSource).filter(DataSource.key == key).first() is None:
            db.add(DataSource(
                key=key, name=spec["name"], type="gov_site",
                class_path="app.collectors.generic_site.GenericSiteCollector",
                enabled=spec.get("enabled", True), priority=spec.get("priority", 100),
                scope_region_codes=spec["scope"],
                config_json=_generic_config(
                    spec["name"], spec["config"]["list_urls"], spec["scope"],
                    keywords=spec["config"].get("keywords"),
                    content_selectors=spec["config"].get("content_selectors"),
                    max_articles=spec["config"].get("max_articles", 8),
                    link_rule=spec["config"].get("link_rule"),
                ),
            ))
            state = "启用" if spec.get("enabled", True) else "已配置(暂停)"
            print(f"[init_db] 已插入城市/县级源: {spec['name']} ({key}) -> {spec['scope']} [{state}]")
        else:
            print(f"[init_db] 城市/县级源已存在，跳过: {key}")


def init() -> None:
    # 安全网：确保表存在（幂等）
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 管理员（bcrypt 加密）
        admin = db.query(User).filter(User.username == settings.init_admin_username).first()
        if admin is None:
            db.add(
                User(
                    username=settings.init_admin_username,
                    password_hash=hash_password(settings.init_admin_password),
                    role="admin",
                )
            )
            print(f"[init_db] 已创建管理员用户: {settings.init_admin_username}")
        else:
            print(f"[init_db] 管理员用户已存在，跳过: {settings.init_admin_username}")

        _seed_regions(db)
        _seed_data_sources(db)
        _seed_keywords(db)
        _seed_sensitive_keywords(db)

        db.commit()
        print("[init_db] 初始化完成。")
    except IntegrityError:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init()
