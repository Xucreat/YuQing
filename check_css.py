import pathlib, glob
css_files = list(pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\static\assets").glob("Propagation-*.css"))
if css_files:
    css = css_files[0].read_text(encoding="utf-8")
    print(f"File: {css_files[0].name} ({len(css)} bytes)")
    for c in ["overflow:hidden", "min-height:0", "flex:1"]:
        found = c in css
        print(f"  {c}: {'OK' if found else 'MISSING'}")
