import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\api\opinions.py")
t = p.read_text(encoding="utf-8")
# Add import
t = t.replace(
    "from sqlalchemy import func, or_, select",
    "from sqlalchemy import func, or_, select, delete as sa_delete"
)
# Fix the delete
t = t.replace(
    'db.query(EventOpinion).where(EventOpinion.opinion_id == opinion_id).delete(synchronize_session=False)',
    'db.execute(sa_delete(EventOpinion).where(EventOpinion.opinion_id == opinion_id))\n    db.flush()'
)
p.write_text(t, encoding="utf-8")
print("Fixed delete_opinion to use db.execute")
