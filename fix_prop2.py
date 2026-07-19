import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\frontend\src\views\Propagation.vue")
t = p.read_text(encoding="utf-8")
lines = t.split("\n")
bt = chr(96)
ds = chr(36)
for i, line in enumerate(lines):
    if "ElMessage.success(" in line and "data.nodes_created" in line:
        lines[i] = f"      ElMessage.success({bt}{chr(20256)}{chr(25773)}{chr(38142)}{chr(26500)}{chr(24314)}{chr(23436)}{chr(25104)}{chr(65306)}{chr(21019)}{chr(24314)} {ds}{{data.nodes_created}} {chr(20010)}{chr(33410)}{chr(28857)}{bt})"
        print(f"Fixed line {i+1}")
    if "ElMessage.success(" in line and "nodes_created" in line:
        lines[i] = f"      ElMessage.success({bt}{chr(20256)}{chr(25773)}{chr(38142)}{chr(26500)}{chr(24314)}{chr(23436)}{chr(25104)}{chr(65306)}{chr(21019)}{chr(24314)} {ds}{{data.nodes_created}} {chr(20010)}{chr(33410)}{chr(28857)}{bt})"
        print(f"Fixed line {i+1} (alt)")
t = "\n".join(lines)
p.write_text(t, encoding="utf-8")
print("Done fixing propagation")
