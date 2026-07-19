import pathlib

# --- P1-2: Fix opinion delete to cascade-clean ---
p1 = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\api\opinions.py")
t1 = p1.read_text(encoding="utf-8")

# Add imports at top
t1 = t1.replace(
    "from app.models.opinion import Opinion\nfrom app.models.region import Region",
    "from app.models.opinion import Opinion\nfrom app.models.region import Region\nfrom app.models.event_opinion import EventOpinion\nfrom app.models.alert import AlertRecord"
)

# Replace the delete function
old_delete = '''@opinions_router.delete("/{opinion_id}", status_code=status.HTTP_200_OK)
def delete_opinion(opinion_id: int, db: Session = Depends(get_db)) -> dict:
    """刪除舆情（MVP 保留）。不存在返回 404。"""
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opinion not found",
        )
    db.delete(opinion)
    db.commit()
    return {"detail": "Opinion deleted", "id": opinion_id}'''

new_delete = '''@opinions_router.delete("/{opinion_id}", status_code=status.HTTP_200_OK)
def delete_opinion(opinion_id: int, db: Session = Depends(get_db)) -> dict:
    """刪除舆情（MVP 保留）。不存在返回 404。"""
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opinion not found",
        )

    # Cascade-clean: delete event_opinions links first
    db.query(EventOpinion).where(EventOpinion.opinion_id == opinion_id).delete()
    # Null out alert_record references
    db.query(AlertRecord).where(AlertRecord.opinion_id == opinion_id).update(
        {"opinion_id": None}, synchronize_session=False
    )
    # Now safe to delete the opinion
    db.delete(opinion)
    db.commit()
    return {"detail": "Opinion deleted", "id": opinion_id}'''

if old_delete in t1:
    t1 = t1.replace(old_delete, new_delete)
    p1.write_text(t1, encoding="utf-8")
    print("P1-2: Opinion delete now cascade-cleans")
else:
    print("P1-2: Delete pattern not found - checking")
    if "def delete_opinion" in t1:
        print("  delete_opinion function exists")
    else:
        print("  delete_opinion function NOT found")

# --- P1-3: Fix Alert tab switching ---
p3 = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\frontend\src\views\Alerts.vue")
t3 = p3.read_text(encoding="utf-8")
# Add a watch on activeTab
old_watch = "import { onMounted, ref, reactive } from 'vue'"
new_watch = "import { onMounted, ref, reactive, watch } from 'vue'"
t3 = t3.replace(old_watch, new_watch)

# Add watcher after the onMounted call
old_onmounted = "onMounted(() => { loadRules() })"
new_onmounted = '''onMounted(() => { loadRules() })

watch(activeTab, (tab) => {
  if (tab === 'records') loadRecords()
})'''
t3 = t3.replace(old_onmounted, new_onmounted)
p3.write_text(t3, encoding="utf-8")
print("P1-3: Alert tab switching now auto-loads records")

