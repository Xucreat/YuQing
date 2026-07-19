import pathlib
# Switch to mock mode
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\.env")
t = p.read_text(encoding="utf-8")
t = t.replace("COLLECTOR_TYPE=government", "COLLECTOR_TYPE=mock")
p.write_text(t, encoding="utf-8")
print(".env: switched to COLLECTOR_TYPE=mock")
