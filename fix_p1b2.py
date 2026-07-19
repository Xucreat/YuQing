import pathlib
p = pathlib.Path(r"C:\Users\Administrator\Desktop\YQ\backend\app\api\opinions.py")
t = p.read_text(encoding="utf-8")

# Match on the function structure, not the garbled Chinese comment
old = """@opinions_router.delete("/{opinion_id}", status_code=status.HTTP_200_OK)
def delete_opinion(opinion_id: int, db: Session = Depends(get_db)) -> dict:"""

# Find the start of delete_opinion
idx = t.find(old)
if idx == -1:
    # Try without dict return annotation
    old2 = '@opinions_router.delete("/{opinion_id}", status_code=status.HTTP_200_OK)\ndef delete_opinion(opinion_id: int, db: Session = Depends(get_db)) -> dict:'
    idx = t.find(old2)
    
if idx >= 0:
    # Find the end of this function (next empty line before another decorator or end of file)
    end_idx = t.find("\n\n@", idx + len(old))
    if end_idx == -1:
        end_idx = len(t)
    
    new_func = '''@opinions_router.delete("/{opinion_id}", status_code=status.HTTP_200_OK)
def delete_opinion(opinion_id: int, db: Session = Depends(get_db)) -> dict:
    """Delete opinion with cascade cleanup of related records."""
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
    
    t = t[:idx] + new_func + t[end_idx:]
    p.write_text(t, encoding="utf-8")
    print("P1-2: Opinion delete function replaced with cascade-clean version")
else:
    print("P1-2: Could not find delete_opinion function signature")
