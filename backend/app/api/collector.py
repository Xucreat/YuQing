"""Collector 閲囬泦鎺ュ彛锛圥hase 3A锛夈€?

璺敱锛堟寕杞藉湪 /api 涓嬶紝鐢?main.py 缁熶竴鍔犲墠缂€锛夛細
  POST   /collector/run     瑙﹀彂涓€娆￠噰闆?+ 鑷姩 AI 鍒嗘瀽闂幆锛圔earer JWT锛?
  GET    /collector/status  鏌ヨ閲囬泦鐘舵€侊紙Bearer JWT锛屽唴瀛橈紝閲嶅惎涓㈠け锛?

涓ユ牸鑼冨洿锛堟湰闃舵锛夛細
- 浠呫€屾墜鍔ㄨЕ鍙戜竴娆￠噰闆嗐€嶃€備笉鍋氬畾鏃?/ Celery / Redis / 浜嬩欢鑱氬悎 / 鍓嶇銆?
- 涓氬姟涓嶇洿鎺ヨ皟鐢?DeepSeek / Provider锛岀粺涓€缁?CollectorService -> AIService銆?
- 閲囬泦鐘舵€佸瓨鍐呭瓨锛堣 collectors.service._COLLECTOR_STATUS锛夛紝閲嶅惎涓㈠け銆?
  涓嶆寔涔呭寲锛涗唬鐮佷笌 docs 宸叉敞鏄?Phase 3A 涓存椂瀹炵幇銆?
- 涓嶄慨鏀规暟鎹簱缁撴瀯 / 涓嶆柊澧炶縼绉汇€?
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.collectors.service import (
    CollectorService,
    CollectorThrottled,
    get_collector_status,
)
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.collector import CollectorRunResponse, CollectorStatusResponse

collector_router = APIRouter(
    tags=["collector"],
    # 鍏ㄩ儴閲囬泦鎺ュ彛鍧囬渶鐧诲綍锛圔earer JWT锛?
    dependencies=[Depends(get_current_user)],
)


@collector_router.post(
    "/run",
    response_model=CollectorRunResponse,
    status_code=status.HTTP_200_OK,
)
def run_collector(
    response: Response,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> CollectorRunResponse:
    """瑙﹀彂涓€娆￠噰闆?+ 鑷姩 AI 鍒嗘瀽闂幆銆?

    娴佺▼锛氭寜 settings.collector_type 閫夋嫨 Collector锛坓overnment / mock锛?
          -> Collector.fetch() -> 鎸?url 鍘婚噸 -> 寤?Opinion(pending)
          -> AIService.analyze -> 鍐欏洖瀛楁 + 鐘舵€佹祦杞?completed/failed)銆?
    杩斿洖锛歝ollector_type锛堥噰闆嗘柟寮忥級/ created / analyzed / failed銆?

    Phase 3B锛氭斂搴滅綉绔欓噰闆?5 绉掑唴閲嶅瑙﹀彂 鈫?杩斿洖 429锛坰uccess=false锛夛紝
    閬垮厤璇搷浣滆繛缁姹傛斂搴滅綉绔欙紙涓嶄娇鐢?500锛夈€?
    """
    service = CollectorService()
    try:
        result = service.collect_and_analyze(db)
    except CollectorThrottled:
        # 5 绉掗槻鎶栵細杩囦簬棰戠箒 鈫?429 Too Many Requests锛堜笉鍒や负鏈嶅姟閿欒锛夈€?
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return CollectorRunResponse(
            success=False,
            collector_type=service.collector_type,
            message="collector running too frequently",
        )
    return CollectorRunResponse(
        success=True,
        collector_type=result.collector_type,
        fetched_raw=result.fetched_raw,
        created=result.created,
        analyzed=result.analyzed,
        failed=result.failed,
        message=(
            f"閲囬泦瀹屾垚锛氭姄鍙杮result.fetched_raw}鏉★紝鏂板{result.created}鏉★紝"
            f"鍒嗘瀽{result.analyzed}鏉?
            + (f"锛寋result.failed}鏉″垎鏋愬け璐? if result.failed > 0 else "")
            + ("锛涙棤鏂板鏁版嵁锛堝彲鑳界綉绔欎笉鍙揪鎴栨暟鎹湭鏇存柊锛? if result.created == 0 else "")
        ),
    )


@collector_router.get(
    "/status",
    response_model=CollectorStatusResponse,
    status_code=status.HTTP_200_OK,
)
def collector_status(
    _current_user: User = Depends(get_current_user),
) -> CollectorStatusResponse:
    """鏌ヨ閲囬泦鐘舵€侊紙妯″潡绾у唴瀛橈紝閲嶅惎涓㈠け锛汸hase 3A 涓存椂瀹炵幇锛夈€?""
    st = get_collector_status()
    return CollectorStatusResponse(
        last_run=st.get("last_run"),
        total_collected=st.get("total_collected", 0),
        collector_type=st.get("collector_type"),
    )


