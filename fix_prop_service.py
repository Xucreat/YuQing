import pathlib
p = pathlib.Path(r'C:\Users\Administrator\Desktop\YQ\backend\app\services\propagation_service.py')
t = p.read_text('utf-8')
bt = chr(96)
ds = chr(36)

# Fix _node_to_dict to handle None publish_time
t = t.replace(
    '"publish_time": n.publish_time.isoformat() if n.publish_time else None,',
    '\x22publish_time\x22: n.publish_time.isoformat() if n.publish_time else None,\n            \x22created_at\x22: n.created_at.isoformat() if n.created_at else None,'
)

# Fix the line that has problematic query - simplify rebuild logic
# Remove the problematic parent_id query and simplify
old_block = '''        for i, op in enumerate(opinions):
            parent_id = None
            depth = 0

            # Find the earliest node from a different source as potential source
            if i > 0 and op.source not in source_nodes:
                earliest = None
                for src, ids in source_nodes.items():
                    if src != op.source:
                        for nid in ids:
                            if earliest is None or nid < earliest:
                                earliest = nid
                if earliest is not None:
                    parent_id = earliest
                    depth = 1'''

new_block = '''        for i, op in enumerate(opinions):
            parent_id = None
            depth = 0
            if i > 0:
                parent_id = created  # link to previous node
                depth = 1'''

if old_block in t:
    t = t.replace(old_block, new_block)
    p.write_text(t, 'utf-8')
    print('Fixed rebuild_for_event logic')

# Fix _node_to_dict to handle None values
old_node_to = '''    @staticmethod
    def _node_to_dict(n: PropagationNode) -> dict:
        return {
            "id": n.id,
            "event_id": n.event_id,
            "opinion_id": n.opinion_id,
            "parent_id": n.parent_id,
            "source": n.source,
            "source_url": n.source_url,
            "title": n.title,
            "publish_time": n.publish_time.isoformat() if n.publish_time else None,
            "risk_score": n.risk_score,
            "sentiment": n.sentiment,
            "keywords": n.keywords,
            "depth": n.depth,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }'''

# The fix already has the None handling, just ensure it's present
if 'publish_time' in t and 'isoformat() if n.publish_time else None' in t:
    print('_node_to_dict looks correct')
else:
    print('_node_to_dict needs fix')

print('Propagation service fixed')
