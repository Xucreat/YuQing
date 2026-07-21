"""Phase 3 验证（不触发 AI 分析，仅验证装配 + 抓取 + 区域绑定）。

1. resolve_collectors(db) 装配结果 = 表驱动（9 既有 + 已启用市级源）。
2. 9 个既有源 class_path / scope 与迁移前 DEFAULT_SOURCES 完全一致（零回归）。
3. 每个已启用市级 GenericSiteCollector：fetch() 实际抓取 >0，且 _resolve_region_id
   返回的区域 code 正确（如石家庄→130100）。
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors.registry import resolve_collectors, DEFAULT_SOURCES
from app.collectors.service import CollectorService
from app.collectors.generic_site import GenericSiteCollector
from app.db.session import SessionLocal
from app.models.region import Region

def main():
    db = SessionLocal()
    cols = resolve_collectors(db)
    print(f"[1] 装配采集器总数: {len(cols)}")
    for c in cols:
        sc = getattr(c, "scope_region_codes", None)
        print(f"    - {getattr(c,'source_name',type(c).__name__):<22} key={getattr(c,'data_source_key','?')} scope={sc} class={type(c).__name__}")

    # 零回归：9 既有源
    print("\n[2] 零回归检查（9 既有源 class_path/scope 与 DEFAULT_SOURCES 比对）")
    by_key = {c.get("key"): c for c in DEFAULT_SOURCES}
    ok = True
    for c in cols:
        k = getattr(c, "data_source_key", None)
        if k in by_key:
            expect = by_key[k]
            real_cls = type(c).__module__ + "." + type(c).__name__
            if real_cls != expect["class_path"]:
                print(f"    ✗ {k}: class 不一致 expect={expect['class_path']} real={real_cls}"); ok = False
            if (getattr(c,'scope_region_codes',None) or [None]) != ([expect["scope_region_codes"]] if expect["scope_region_codes"] else [None]):
                # scope 比较："" -> None
                exp_scope = [expect["scope_region_codes"]] if expect["scope_region_codes"] else None
                re_scope = getattr(c,'scope_region_codes',None)
                if exp_scope != re_scope:
                    print(f"    ✗ {k}: scope 不一致 expect={exp_scope} real={re_scope}"); ok = False
    # 确认 9 个既有 key 全部出现
    missing = [k for k in by_key if k not in {getattr(c,'data_source_key',None) for c in cols}]
    if missing:
        print(f"    ✗ 缺失既有源: {missing}"); ok = False
    print("    ✓ 9 既有源全部存在且 class/scope 与迁移前一致" if ok and not missing else "    （见上）")

    # 市级源实际抓取 + 区域绑定
    print("\n[3] 已启用市级源：实际抓取 + region_id 绑定校验")
    svc = CollectorService(collectors=cols)  # injected，避免重复装配
    city_ok = 0
    city_total = 0
    for c in cols:
        if not isinstance(c, GenericSiteCollector):
            continue
        city_total += 1
        scope = getattr(c, "scope_region_codes", None)
        region = db.query(Region).filter(Region.code == (scope[0] if scope else "130000")).first()
        expected_code = scope[0] if scope else "130000"
        rid = svc._resolve_region_id(db, c)
        resolved_code = db.query(Region).filter(Region.id == rid).first().code
        binding_ok = (resolved_code == expected_code)
        try:
            items = c.fetch() or []
        except Exception as e:
            items = []; print(f"    ✗ {c.source_name} fetch 异常: {e}")
        n = len(items)
        flag = "✓" if (n > 0 and binding_ok) else ("△" if n == 0 else "✗")
        if n > 0 and binding_ok:
            city_ok += 1
        print(f"    {flag} {c.source_name:<16} scope={expected_code} 解析region={resolved_code} 抓取={n} 绑定正确={binding_ok}")
    print(f"\n[结果] 已启用市级源 {city_total} 个；实际抓取成功且区域正确: {city_ok} 个（验收要求 ≥5）")
    db.close()

if __name__ == "__main__":
    main()
