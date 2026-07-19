import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\services\alert_service.py")
t = p.read_text(encoding="utf-8")
t = t.replace(
    'rules = db.query(AlertRule).where(AlertRule.enabled == True).all()',
    'rules = db.query(AlertRule).where(AlertRule.enabled == True).all()\n        print(f"[DEBUG] Found {len(rules)} enabled rules")'
)
t = t.replace(
    'opinions = q.all()',
    'opinions = q.all()\n            print(f"[DEBUG] Rule {rule.id}: {len(opinions)} opinions matched")'
)
p.write_text(t, encoding="utf-8")
print("Debug prints added")
