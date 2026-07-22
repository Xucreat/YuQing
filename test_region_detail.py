import sys
sys.path.insert(0, 'backend')
from app.db.session import SessionLocal
from app.services.dashboard_service import get_dashboard_stats

db = SessionLocal()
for days in (7, 30):
    d = get_dashboard_stats(db, days=days)
    print(f"===== days={days} =====")
    print("regions (province rollup):")
    for r in d["regions"]:
        print(f"   {r['region_name']:<10} {r['count']}")
    print("region_detail (city/county):")
    for r in d["region_detail"]:
        print(f"   {r['region_name']:<14} {r['count']}")
db.close()
