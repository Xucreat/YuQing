import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\collectors\service.py")
t = p.read_text(encoding="utf-8")
old = '    collector_type: str = ""'
new = '    collector_type: str = ""\n    fetched_raw: int = 0'
t = t.replace(old, new)
p.write_text(t, encoding="utf-8")
print("Added fetched_raw to dataclass")
