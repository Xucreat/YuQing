import sys
sys.path.insert(0, 'backend')
from app.db.session import SessionLocal
from sqlalchemy import select, func
from app.models.region import Region
from app.models.opinion import Opinion

db = SessionLocal()
print("=== regions by level ===")
rows = db.execute(select(Region.level, func.count(Region.id)).group_by(Region.level).order_by(Region.level)).all()
for level, cnt in rows:
    print(f"  {level}: {cnt}")

print("\n=== all regions ===")
rows = db.execute(select(Region.code, Region.name, Region.level, Region.parent_code).order_by(Region.code)).all()
for code, name, level, pc in rows:
    print(f"  {code:>8} {name:<16} {level:<8} parent={pc}")

print("\n=== opinions region_id distribution (top 20) ===")
rows = db.execute(
    select(Opinion.region_id, func.count(Opinion.id))
    .group_by(Opinion.region_id).order_by(func.count(Opinion.id).desc()).limit(20)
).all()
for rid, cnt in rows:
    r = db.get(Region, rid)
    nm = r.name if r else "??"
    lvl = r.level if r else "??"
    print(f"  region_id={rid} count={cnt} name={nm} level={lvl}")

print("\n=== total opinions ===")
print("  ", db.scalar(select(func.count(Opinion.id))))
db.close()
