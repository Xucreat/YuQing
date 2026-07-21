"""导出 data_sources 表为 JSON + CSV（Phase 3 迁移备份 / 交付物）。"""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
from app.db.session import SessionLocal
from app.models.data_source import DataSource

OUT_JSON = _BACKEND_ROOT / "phase3_data_sources_backup.json"
OUT_CSV = _BACKEND_ROOT / "phase3_data_sources_backup.csv"

def main():
    db = SessionLocal()
    rows = db.query(DataSource).order_by(DataSource.priority.asc(), DataSource.id.asc()).all()
    data = []
    for r in rows:
        data.append({
            "id": r.id, "key": r.key, "name": r.name, "type": r.type,
            "class_path": r.class_path, "enabled": r.enabled, "priority": r.priority,
            "scope_region_codes": r.scope_region_codes, "config_json": r.config_json,
        })
    db.close()
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id","key","name","type","class_path","enabled","priority","scope_region_codes","config_json"])
        w.writeheader()
        for d in data:
            w.writerow(d)
    print(f"已导出 {len(data)} 条 data_sources -> {OUT_JSON.name} / {OUT_CSV.name}")

if __name__ == "__main__":
    main()
