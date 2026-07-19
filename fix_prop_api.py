import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\api\propagation.py")
t = p.read_text(encoding="utf-8")
t = t.replace(
    "from app.schemas.propagation import PropagationGraphResponse, PropagationRebuildResponse",
    "from app.schemas.propagation import PropagationGraphResponse, PropagationRebuildResponse"
)
old1 = '@propagation_router.get("/graph/{event_id}")'
new1 = '@propagation_router.get("/graph/{event_id}", response_model=PropagationGraphResponse)'
t = t.replace(old1, new1)
print("get_graph updated:", old1 in t, new1 in t)
p.write_text(t, encoding="utf-8")
print("Propagation API updated")
