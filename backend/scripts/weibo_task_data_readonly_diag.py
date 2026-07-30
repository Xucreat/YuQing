"""微博数据源 - 八爪鱼任务数据只读诊断（复用真实采集器鉴权，纯 GET）。

严格只读：
  - 仅调用 GET /data/notexported 与 GET /data/all
  - 绝不调用 /data/notexported/update（标记导出）
  - 绝不调用任何清空/删除/修改任务接口
不修改任何代码、不写数据库。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

# 自举：把 backend 目录加入 sys.path，使 app 包可导入（与 db_identity_check.py 同法）
BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.collectors.weibo_octopus_collector import WeiboOctopusCollector  # noqa: E402
from app.core.config import settings  # noqa: E402

BASE = (settings.bazhu_base_url or "https://openapi.bazhuayu.com").rstrip("/")
TASK_ID = settings.bazhu_task_id or ""
SIZE = int(settings.bazhu_fetch_size or 100)


def main() -> None:
    if not TASK_ID:
        print("[diag] 错误：BAZHU_TASK_ID 为空，无法定位任务")
        return

    print(f"[diag] base_url={BASE}")
    print(f"[diag] task_id={TASK_ID}")
    print(f"[diag] auth_mode={'BAZHU_API_KEY' if settings.bazhu_api_key else 'username/password'}")

    col = WeiboOctopusCollector()  # 仅读取 settings，不发起采集
    token = col._get_token()  # 复用真实鉴权逻辑
    print(f"[diag] token 获取成功 (len={len(token)})")
    headers = {"Authorization": f"Bearer {token}"}

    result = {
        "base_url": BASE,
        "task_id": TASK_ID,
        "auth_mode": "BAZHU_API_KEY" if settings.bazhu_api_key else "username/password",
        "readonly": True,
        "called_endpoints": [],
        "notexported": None,
        "all": None,
        "comparison": None,
        "conclusion": None,
    }

    # 1) 只读 GET /data/notexported
    r1 = col.session.get(
        f"{BASE}{col.path_notexported}",
        params={"taskId": TASK_ID, "size": SIZE},
        headers=headers,
        timeout=col.timeout,
    )
    r1.raise_for_status()
    b1 = r1.json() or {}
    d1 = b1.get("data") or {}
    ne_rows = d1.get("data") or d1.get("dataList") or []
    ne_rows = ne_rows if isinstance(ne_rows, list) else []
    result["called_endpoints"].append("/data/notexported (GET, 只读)")
    result["notexported"] = {
        "http_status": r1.status_code,
        "raw_total": d1.get("total", "N/A"),
        "raw_current": d1.get("current", "N/A"),
        "returned_rows": len(ne_rows),
        "sample_keys": sorted(ne_rows[0].keys()) if ne_rows else [],
    }
    print(f"[notexported] http={r1.status_code} total={d1.get('total')} current={d1.get('current')} rows={len(ne_rows)}")

    # 2) 只读 GET /data/all（分页累加，最多 20 页）
    all_total = None
    all_rows = 0
    page = 1
    last_status = None
    while page <= 20:
        r2 = col.session.get(
            f"{BASE}/data/all",
            params={"taskId": TASK_ID, "size": SIZE, "page": page},
            headers=headers,
            timeout=col.timeout,
        )
        r2.raise_for_status()
        last_status = r2.status_code
        b2 = r2.json() or {}
        d2 = b2.get("data") or {}
        if page == 1:
            all_total = d2.get("total", "N/A")
            result["called_endpoints"].append("/data/all (GET, 只读)")
        rows = d2.get("data") or []
        if not isinstance(rows, list):
            break
        all_rows += len(rows)
        if len(rows) < SIZE:
            break
        page += 1
    result["all"] = {
        "http_status": last_status,
        "raw_total": all_total,
        "returned_rows_sum": all_rows,
        "pages_pulled": page,
    }
    print(f"[all] http={last_status} raw_total={all_total} returned_rows_sum={all_rows} pages={page}")

    # 3) 对比结论
    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    ne_n = _int(result["notexported"]["raw_total"])
    al_n = _int(result["all"]["raw_total"])

    if ne_n == 0 and al_n == 0:
        concl = "任务内无任何数据（notexported=0 且 all=0）：八爪鱼任务尚未采集到微博，或任务/模板未运行。"
    elif ne_n == 0 and al_n is not None and al_n > 0:
        concl = (
            f"数据存在但未进入未导出队列：/data/all 共 {al_n} 条，但 /data/notexported=0。"
            "可能已全部被标记为导出（导出队列清空），或任务导出状态需重置。"
            "可选对策：① 在八爪鱼平台重置/重跑该任务导出状态；"
            "② 新建一个未导出任务并使用其 TASK_ID；"
            "③ 评估将采集器数据源改为 /data/all（需配合 external_id 去重避免重复入库，且 /data/all 不应标记导出）。"
        )
    elif ne_n is not None and ne_n > 0:
        concl = f"未导出队列有数据：notexported={ne_n}，all={al_n}。可直接采集（此前 total=0 属瞬时/已消费状态）。"
    else:
        concl = "无法判定：接口返回结构异常，请查看 notexported/all 原始字段。"

    result["comparison"] = {
        "notexported_total": result["notexported"]["raw_total"],
        "all_total": result["all"]["raw_total"],
        "delta": (al_n - ne_n) if (isinstance(al_n, int) and isinstance(ne_n, int)) else "N/A",
    }
    result["conclusion"] = concl
    result["generated_at"] = datetime.now(timezone.utc).isoformat()

    out_path = os.path.join(BACKEND, "weibo_task_data_readonly_diag.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    print("\n=== 结论 ===")
    print(concl)
    print(f"[diag] 证据已写入: {out_path}")


if __name__ == "__main__":
    main()
