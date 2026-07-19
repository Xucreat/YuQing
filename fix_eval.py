import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\services\alert_service.py")
t = p.read_text(encoding="utf-8")

old = """            if rule.keywords:
                for kw in rule.keywords.split(","):
                    kw = kw.strip()
                    if kw:
                        like = f"%{kw}%"
                        q = q.where(
                            or_(
                                Opinion.keywords.ilike(like),
                                Opinion.title.ilike(like),
                                Opinion.content.ilike(like),
                            )
                        )"""

new = """            if rule.keywords:
                kw_conds = []
                for kw in rule.keywords.split(","):
                    kw = kw.strip()
                    if kw:
                        like = f"%{kw}%"
                        kw_conds.append(
                            or_(
                                Opinion.keywords.ilike(like),
                                Opinion.title.ilike(like),
                                Opinion.content.ilike(like),
                            )
                        )
                if kw_conds:
                    q = q.where(or_(*kw_conds))"""

if old in t:
    t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    print("Keyword matching fixed: OR logic instead of AND")
else:
    print("Pattern not found - trying alternate search")
    for i, line in enumerate(t.split("\n")):
        if "for kw in rule.keywords" in line:
            print(f"  Found at line {i+1}: {line.strip()}")
