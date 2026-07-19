import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\schemas\propagation.py")
t = p.read_text(encoding="utf-8")

# Add SourceSummaryItem before PropagationGraphResponse
new_item = """
class SourceSummaryItem(BaseModel):
    source: str
    count: int
"""
t = t.replace(
    "class PropagationGraphResponse(BaseModel):",
    new_item + "\nclass PropagationGraphResponse(BaseModel):"
)

# Fix source_summary type
t = t.replace("source_summary: List[dict] = []", "source_summary: List[SourceSummaryItem] = []")

p.write_text(t, encoding="utf-8")
print("Schema fixed: added SourceSummaryItem, fixed List[dict]")

# Also add from_attributes to PropagationLink to be safe
t2 = p.read_text(encoding="utf-8")
if "class PropagationLink(BaseModel):" in t2 and "model_config" not in t2[t2.index("class PropagationLink"):t2.index("class PropagationLink")+200]:
    t2 = t2.replace(
        "class PropagationLink(BaseModel):",
        "class PropagationLink(BaseModel):\n    model_config = ConfigDict(from_attributes=True)"
    )
    p.write_text(t2, encoding="utf-8")
    print("Added from_attributes to PropagationLink")
print("All schema fixes done")
