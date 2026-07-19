import pathlib

BASE = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ")

# ===== FIX 2: Propagation - add loadEvents after rebuild =====
fp = BASE / "frontend/src/views/Propagation.vue"
t = fp.read_text(encoding="utf-8")
lines = t.split("\n")
for i, line in enumerate(lines):
    if "await selectEvent(selectedEvent.value)" in line and i > 0:
        if "loadEvents" not in lines[i-1]:
            indent = line[:len(line) - len(line.lstrip())]
            lines.insert(i, indent + "await loadEvents()")
            t = "\n".join(lines)
            fp.write_text(t, encoding="utf-8")
            print(f"FIX 2: Added loadEvents() before selectEvent at line {i+1}")
            break
else:
    print("FIX 2: selectEvent call not found")

# ===== FIX 3: ID columns - change prop=id to type=index =====
files_to_fix = [
    ("frontend/src/views/Opinions.vue", "Opinions"),
    ("frontend/src/views/Events.vue", "Events"),
    ("frontend/src/views/Alerts.vue", "Alerts"),
]
for fname, label in files_to_fix:
    fp2 = BASE / fname
    if fp2.exists():
        t2 = fp2.read_text(encoding="utf-8")
        # Replace the ID column
        t2 = t2.replace("""prop="id" label="ID" width="70" />""", """type="index" label="#" width="60" />""")
        # Also handle the rules table ID
        t2 = t2.replace("""prop="id" label="ID" width="70" />""", """type="index" label="#" width="60" />""")
        fp2.write_text(t2, encoding="utf-8")
        print(f"FIX 3: {label} - ID column changed to index")
    else:
        print(f"FIX 3: {fname} not found")

# ===== FIX 4: Alert - widen operation column =====
fa = BASE / "frontend/src/views/Alerts.vue"
if fa.exists():
    ta = fa.read_text(encoding="utf-8")
    if "v-if=" in ta and "row.handled" in ta:
        print("FIX 4: Handle button code present")
    else:
        print("FIX 4: Handle button code MISSING")
