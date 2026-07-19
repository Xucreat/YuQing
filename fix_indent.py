import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\services\propagation_service.py")
lines = p.read_text(encoding="utf-8").split("\n")
cleaned = []
skip_until_close = False
for i, line in enumerate(lines):
    stripped = line.rstrip()
    if "def _node_to_dict" in stripped:
        # Start of broken method
        skip_until_close = True
        # Write correct method
        cleaned.append("    @staticmethod")
        cleaned.append("    def _node_to_dict(n: PropagationNode) -> dict:")
        cleaned.append("        return {")
        cleaned.append('            "id": n.id,')
        cleaned.append('            "event_id": n.event_id,')
        cleaned.append('            "opinion_id": n.opinion_id,')
        cleaned.append('            "parent_id": n.parent_id,')
        cleaned.append('            "source": n.source,')
        cleaned.append('            "source_url": n.source_url,')
        cleaned.append('            "title": n.title,')
        cleaned.append('            "publish_time": n.publish_time.isoformat() if n.publish_time else None,')
        cleaned.append('            "risk_score": n.risk_score,')
        cleaned.append('            "sentiment": n.sentiment,')
        cleaned.append('            "keywords": n.keywords,')
        cleaned.append('            "depth": n.depth,')
        cleaned.append('            "created_at": n.created_at.isoformat() if n.created_at else None,')
        cleaned.append("        }")
        continue
    if skip_until_close:
        # Skip lines of broken method until we hit the closing brace and empty line
        if stripped in ("", "        }"):
            skip_until_close = False
        continue
    cleaned.append(line)

p.write_text("\n".join(cleaned), encoding="utf-8")
print("Propagation service indentation fixed")
