import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\.env")
t = p.read_text(encoding="utf-8")
t = t.replace("COLLECTOR_TYPE=mock", "COLLECTOR_TYPE=government")
p.write_text(t, encoding="utf-8")
print(".env: restored to COLLECTOR_TYPE=government")
