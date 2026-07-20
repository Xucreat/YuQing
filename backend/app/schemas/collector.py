"""Collector 鎺ュ彛鍝嶅簲妯″瀷锛圥hase 3A / 3B锛夈€?
浠呭仛搴忓垪鍖栵紝涓嶇洿鎺ヨ繑鍥?ORM / dict銆?- CollectorRunResponse锛氬崟娆￠噰闆嗚繍琛岀粨鏋滐紙created / analyzed / failed锛夈€?- CollectorStatusResponse锛氶噰闆嗙姸鎬侊紙鍐呭瓨锛岄噸鍚涪澶憋級銆?
Phase 3B锛氭柊澧?collector_type 琛ㄧず**閲囬泦鏂瑰紡**锛坓overnment / mock锛夛紝
涓庢暟鎹簱 Opinion.source锛堟柊闂绘潵婧愶紝濡傘€屽ぇ鍘傚幙鏀垮簻缃戠珯銆嶏級鍖哄垎锛屽嬁娣锋穯銆?"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CollectorRunResponse(BaseModel):
    """閲囬泦杩愯缁撴灉銆?""

    success: bool = True
    collector_type: str = ""  # 閲囬泦鏂瑰紡锛歡overnment | mock锛堥潪鏁版嵁鏉ユ簮锛?    created: int = 0       # 鏈鏂板 Opinion 鏁?    analyzed: int = 0
    fetched_raw: int = 0  # total items scraped (before dedup)       # AI 鍒嗘瀽鎴愬姛锛坈ompleted锛夋暟
    failed: int = 0         # 澶辫触鏁?= created - analyzed锛堣褰曚繚鐣欙紝鐘舵€?failed锛?    message: str = ""


class CollectorStatusResponse(BaseModel):
    """閲囬泦鐘舵€侊紙妯″潡绾у唴瀛橈紝閲嶅惎涓㈠け锛汸hase 3A 涓存椂瀹炵幇锛夈€?""

    last_run: Optional[datetime] = None
    total_collected: int = 0
    collector_type: Optional[str] = None  # 鏈€杩戜竴娆￠噰闆嗘柟寮忥紙government / mock锛?
