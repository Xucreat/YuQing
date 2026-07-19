import sys; sys.path.insert(0, r"C:\Users\Administrator\Desktop\YQ\backend")
from app.db.session import SessionLocal
from app.models.alert import AlertRule, AlertRecord
from app.services.alert_service import AlertService

db = SessionLocal()

# Delete broken rule
old = db.get(AlertRule, 4)
if old:
    db.delete(old)
    db.commit()
    print("Broken rule deleted")

# Create proper rule with correct UTF-8
rule = AlertRule(
    name="高风险安全舆情监控",
    description="监控风险评分>=80且涉及安全事故、火灾、伤亡、谣言等高危关键词的舆情",
    risk_threshold=80,
    keywords="事故,火灾,伤亡,死亡,谣言,群体,维权,爆炸,中毒",
    sources="",
    risk_level="critical",
    enabled=True,
)
db.add(rule)
db.commit()
db.refresh(rule)
print(f"Created: id={rule.id} name={rule.name!r} keywords={rule.keywords!r}")

# Run evaluation
result = AlertService.evaluate(db)
AlertService.sync_alert_events(db)
print(f"Eval: checked={result['total_checked']} created={result['alerts_created']}")

# Verify records
records = db.query(AlertRecord).order_by(AlertRecord.id).all()
for rec in records:
    print(f"  #{rec.id} [{rec.risk_level}] opinion={rec.opinion_id} event={rec.event_id}")

db.close()
