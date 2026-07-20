"""Collector 閲囬泦鏈嶅姟锛圥hase 3A锛氶噰闆?鈫?鍏ュ簱 鈫?鑷姩 AI 鍒嗘瀽闂幆锛夈€?

鑱岃矗锛?
  1. 璋冨害鍚?Collector.fetch() 鎷垮埌鏍囧噯鍖?dict 鍒楄〃銆?
  2. 鎸?url 鍘婚噸锛坲rl 涓虹┖鏃堕€€鍥?title+publish_time 杈呭姪鍒ゆ柇锛夛紝璺宠繃宸插瓨鍦ㄩ」銆?
  3. 鏂板缓 Opinion锛堥粯璁?risk_score=0 / sentiment=neutral / analysis_status=pending锛夈€?
  4. 璋冪敤 AIService.analyze(title, content) 鍋?AI 鍒嗘瀽骞跺啓鍥炲瓧娈?+ 鐘舵€佹祦杞€?
  5. 鍗曟潯 AI 澶辫触闅旂锛氳鏉＄疆 analysis_status="failed"锛堜繚鐣欐暟鎹簱璁板綍锛夛紝
     涓嶅奖鍝嶅叾浣欐暟鎹紱澶辫触璁℃暟 failed = created - analyzed銆?

璁捐绾︽潫锛堟潵鑷敤鎴风‘璁わ級锛?
- 澶嶇敤 AIService.analyze锛堜笌鎵嬪姩鍒嗘瀽 API 鍏辩敤鍒嗘瀽鑳藉姏锛夛紝涓嶆娊鍙栧叕鍏?
  AIAnalysisHelper锛圡VP 蹇€熼獙璇侊級锛涗絾宸插湪涓嬫柟鏍囨敞 TODO Phase 4 寰呮娊鍙栥€?
- CollectorService 涓嶇洿鎺ヨ皟鐢?DeepSeek / Provider锛岀粺涓€缁?AIService銆?
- 閲囬泦鐘舵€佸瓨**妯″潡绾у唴瀛樺彉閲?*锛堣 _COLLECTOR_STATUS锛夛紝閲嶅惎涓㈠け銆佷笉鎸佷箙鍖栥€?
  # Phase 3A temporary implementation.
  # Persistent collector task history is postponed.
  # Future: 鑻ュ鍔犲畾鏃堕噰闆嗭紝鍐嶈璁?collector_runs 琛ㄣ€?
- 涓嶄慨鏀规暟鎹簱缁撴瀯 / 涓嶆柊澧炶縼绉?/ 涓嶅紩鍏?Celery / Redis / 瀹氭椂浠诲姟銆?
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector
from app.collectors.government_collector import GovernmentCollector
from app.collectors.baidu_news_collector import BaiduNewsCollector
from app.collectors.weibo_collector import WeiboCollector
from app.collectors.hebei_news_collector import HebeiNewsCollector
from app.collectors.mock_collector import MockCollector
from app.collectors.rss_collector import RSSCollector
from app.core.config import settings
from app.models.opinion import Opinion
from app.models.region import Region
from app.models.collector_run import CollectorRun
from app.services.ai import AIService
from app.services.alert_service import AlertService

# ---------------------------------------------------------------------------
# Phase 3A temporary implementation.
# Persistent collector task history is postponed.
# Future: if scheduled collection is added, design a `collector_runs` table.
# ---------------------------------------------------------------------------
_COLLECTOR_STATUS: dict = {
    "last_run": None,   # datetime | None锛屾渶杩戜竴娆￠噰闆嗘椂闂?
    "total_collected": 0,  # int锛岀疮璁￠噰闆嗭紙鏈杩涚▼鍐咃級
    "collector_type": None,  # str | None锛屾渶杩戜竴娆￠噰闆嗘柟寮忥紙government/mock锛?
}

# Phase 3B锛氭斂搴滅綉绔欓噰闆嗛槻鎶栨椂闂存埑锛堟ā鍧楃骇鍐呭瓨锛岄噸鍚涪澶憋級銆?
# 姣忔 government 閲囬泦鍚庢洿鏂帮紱THROTTLE_SECONDS 鍐呴噸澶嶈Е鍙?鈫?CollectorThrottled銆?
_GOV_LAST_RUN_AT: Optional[datetime] = None
THROTTLE_SECONDS = 5.0


class CollectorThrottled(Exception):
    """鏀垮簻缃戠珯閲囬泦瑙﹀彂杩囦簬棰戠箒锛? 绉掗槻鎶栵級锛岀敱 API 灞傝浆 429銆?""


def reset_gov_throttle() -> None:
    """閲嶇疆鏀垮簻閲囬泦闃叉姈鏃堕棿鎴筹紙渚涙祴璇曚娇鐢級銆?""
    global _GOV_LAST_RUN_AT
    _GOV_LAST_RUN_AT = None


def resolve_collectors(collector_type: Optional[str] = None) -> List[BaseCollector]:
    """Resolve default collectors by type (P0: now includes baidu/weibo in production)."""
    ctype = (collector_type or settings.collector_type or "government").lower()
    if ctype == "mock":
        return [MockCollector()]

    # Production: government + baidu news + weibo (all enabled by default)
    collectors: List[BaseCollector] = [GovernmentCollector()]
    if settings.baidu_news_enabled:
        collectors.append(BaiduNewsCollector())
    if settings.weibo_enabled:
        collectors.append(WeiboCollector())
    if settings.hebei_news_enabled:
        collectors.append(HebeiNewsCollector())
    return collectors

@dataclass
class CollectorRunResult:
    """鍗曟閲囬泦杩愯缁撴灉銆?""

    created: int = 0    # 鏈瀹為檯鏂板 Opinion 鏁伴噺
    analyzed: int = 0   # AI 鍒嗘瀽鎴愬姛锛坈ompleted锛夋暟閲?
    collector_type: str = ""
    fetched_raw: int = 0  # 鏈閲囬泦鏂瑰紡锛坓overnment/mock锛?

    def finalize(self) -> "CollectorRunResult":
        # 澶辫触 = 鏂板 - 鍒嗘瀽鎴愬姛锛涘け璐ヨ褰曚繚鐣欏湪鏁版嵁搴擄紙status=failed锛夈€?
        self.failed = max(0, self.created - self.analyzed)
        return self

    # failed 缁?finalize 璁＄畻鍚庡瓨鍦紱澹版槑鍗犱綅閬垮厤 mypy 鎶ユ湭瀹氫箟銆?
    failed: int = 0


def get_collector_status() -> dict:
    """杩斿洖閲囬泦鐘舵€侊紙妯″潡绾у唴瀛橈紝閲嶅惎涓㈠け锛涜涓婃柟 Phase 3A 娉ㄩ噴锛夈€?""
    return dict(_COLLECTOR_STATUS)


class CollectorService:
    """閲囬泦闂幆鏈嶅姟锛歠etch 鈫?鍘婚噸 鈫?寤?Opinion 鈫?AI 鍒嗘瀽 鈫?鐘舵€佹祦杞€?""

    def __init__(
        self,
        collectors: Optional[List[BaseCollector]] = None,
        region_id: Optional[int] = None,
        collector_type: Optional[str] = None,
    ) -> None:
        # 閲囬泦鏂瑰紡锛氭樉寮忎紶鍏?> Pydantic Settings锛坈ollector_type锛夈€?
        self.collector_type: str = (
            collector_type or settings.collector_type or "government"
        ).lower()
        # 榛樿閲囬泦鍣細鎸?collector_type 閫夋嫨锛坓overnment / mock锛夈€?
        # 涔熷彲鏄惧紡娉ㄥ叆 collectors锛堟祴璇曠敤锛夛紝姝ゆ椂 collector_type 浠嶇敤浜庤繑鍥炴爣璇嗐€?
        self.collectors: List[BaseCollector] = (
            collectors if collectors is not None else resolve_collectors(self.collector_type)
        )
        self.region_id: Optional[int] = region_id

        # TODO Phase 4:
        # extract shared opinion analysis workflow
        # reuse by manual analysis API and collector service

    def _uses_government(self) -> bool:
        """鏈閲囬泦鏄惁娑夊強鏀垮簻缃戠珯锛堝喅瀹氭槸鍚﹀惎鐢?5 绉掗槻鎶栵級銆?""
        return any(isinstance(c, GovernmentCollector) for c in self.collectors)

    # ------------------------------------------------------------------
    # 鍐呴儴宸ュ叿
    # ------------------------------------------------------------------
    def _resolve_region_id(self, db: Session) -> int:
        """瑙ｆ瀽缁戝畾鍖哄煙锛氫紭鍏堜娇鐢ㄦ樉寮?region_id锛涘惁鍒欑敤绉嶅瓙鍖哄煙 131028锛堝ぇ鍘傚幙锛夈€?""
        if self.region_id is not None:
            region = db.get(Region, self.region_id)
            if region is None:
                raise RuntimeError(
                    f"Collector region_id={self.region_id} 涓嶅瓨鍦紝璇锋鏌ュ尯鍩熼厤缃€?
                )
            return self.region_id

        # 榛樿锛氱瀛愬尯鍩?澶у巶鍥炴棌鑷不鍘匡紙code=131028锛?
        region = db.query(Region).filter(Region.code == "131028").first()
        if region is None:
            # 鍏滃簳锛氬彇浠绘剰棣栦釜鍖哄煙锛堥伩鍏嶇瀛愮己澶辨椂鏁翠綋澶辫触锛?
            region = db.query(Region).first()
        if region is None:
            raise RuntimeError(
                "鏈厤缃换浣曞尯鍩燂紙region锛夛紝Collector 鏃犳硶缁戝畾 region_id锛?
                "璇峰厛鎵ц init_db.py 鍒濆鍖栫瀛愬尯鍩熴€?
            )
        return region.id

    def _already_exists(self, db: Session, item: dict) -> bool:
        """鍘婚噸鍒ゆ柇锛堜互 opinions.url 涓哄噯锛泆rl 涓虹┖鏃堕€€鍥?title+publish_time锛夈€?""
        url = (item.get("url") or "").strip()
        if url:
            exists = db.query(Opinion).filter(Opinion.url == url).first()
            if exists is not None:
                return True
        # url 涓虹┖锛堟垨璇?url 鏈懡涓級-> 鐢?title + publish_time 杈呭姪鍒ゆ柇
        title = (item.get("title") or "").strip()
        pub = item.get("publish_time")
        exists = (
            db.query(Opinion)
            .filter(
                Opinion.url == "",
                Opinion.title == title,
                Opinion.publish_time == pub,
            )
            .first()
        )
        return exists is not None

    # ------------------------------------------------------------------
    # 涓绘祦绋?
    # ------------------------------------------------------------------

    def collect_and_analyze(self, db: Session) -> CollectorRunResult:
        """Execute one collection + auto AI analysis cycle, returns run result.

        Phase 3B: government site collection uses 5-second throttle.
        """
        global _GOV_LAST_RUN_AT

        # 5-second throttle (government site only)
        if self._uses_government() and _GOV_LAST_RUN_AT is not None:
            elapsed = (datetime.now(timezone.utc) - _GOV_LAST_RUN_AT).total_seconds()
            if elapsed < THROTTLE_SECONDS:
                raise CollectorThrottled("collector running too frequently")

        region_id = self._resolve_region_id(db)
        result = CollectorRunResult(collector_type=self.collector_type)
        ai = AIService()
        start_time = datetime.now(timezone.utc)
        per_collector_stats: dict[str, dict[str, int]] = {}

        for collector in self.collectors:
            name = collector.source_name
            stats = {"fetched_raw": 0, "created": 0, "analyzed": 0}

            items = collector.fetch() or []
            stats["fetched_raw"] = len(items)
            result.fetched_raw += len(items)

            for item in items:
                # 1) Dedup: skip existing
                if self._already_exists(db, item):
                    continue

                # 2) Create Opinion (pending)
                opinion = Opinion(
                    title=(item.get("title") or "").strip(),
                    content=item.get("content") or "",
                    source=(item.get("source") or "").strip() or name,
                    url=(item.get("url") or "").strip(),
                    publish_time=item.get("publish_time"),
                    region_id=region_id,
                    risk_score=0,
                    sentiment="neutral",
                    analysis_status="pending",
                )
                db.add(opinion)
                db.commit()
                result.created += 1
                stats["created"] += 1

                # 3) AI analysis (isolated per-item failure)
                try:
                    analysis = ai.analyze(opinion.title, opinion.content)
                    opinion.summary = analysis.summary
                    opinion.sentiment = analysis.sentiment
                    opinion.risk_score = analysis.risk_score
                    opinion.keywords = ",".join(analysis.keywords)
                    opinion.analysis_suggestion = analysis.suggestion
                    opinion.analysis_status = "completed"
                    opinion.analysis_time = datetime.now(timezone.utc)
                    db.commit()
                    result.analyzed += 1
                    stats["analyzed"] += 1
                except Exception:
                    db.rollback()
                    opinion.analysis_status = "failed"
                    db.add(opinion)
                    db.commit()

            per_collector_stats[name] = stats

        # Write CollectorRun record for each collector
        for cname, stats in per_collector_stats.items():
            failed = stats["created"] - stats["analyzed"]
            cr = CollectorRun(
                collector_name=cname,
                start_time=start_time,
                end_time=datetime.now(timezone.utc),
                fetched_raw=stats["fetched_raw"],
                created=stats["created"],
                analyzed=stats["analyzed"],
                failed=failed,
                status="completed" if failed == 0 and stats["fetched_raw"] > 0 else ("limited" if failed > 0 else "running"),
            )
            db.add(cr)
        db.commit()

        result.finalize()

        # 4) Update in-memory status
        now = datetime.now(timezone.utc)
        _COLLECTOR_STATUS["last_run"] = now
        _COLLECTOR_STATUS["total_collected"] += result.created
        _COLLECTOR_STATUS["collector_type"] = self.collector_type

        if self._uses_government():
            _GOV_LAST_RUN_AT = now

        # Auto-trigger alert evaluation
        try:
            alert_result = AlertService.evaluate(db)
            if alert_result.get("alerts_created", 0) > 0:
                AlertService.sync_alert_events(db)
        except Exception:
            pass

        return result

