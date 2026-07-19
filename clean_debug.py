import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\services\alert_service.py")
t = p.read_text(encoding="utf-8")
lines = t.split("\n")
cleaned = [l for l in lines if "[DEBUG]" not in l]
t2 = "\n".join(cleaned)
p.write_text(t2, encoding="utf-8")
print("Debug prints removed")
