import sys; sys.path.insert(0, r"C:\Users\Administrator\Desktop\YQ\backend")
from app.db.session import SessionLocal
from app.models.propagation import PropagationNode
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRecord
from app.models.event import Event
from app.models.opinion import Opinion

db = SessionLocal()

# FK-safe deletion order
print("Clearing propagation_nodes (null parent_id first)...")
db.query(PropagationNode).update({"parent_id": None}, synchronize_session=False)
deleted = db.query(PropagationNode).delete(synchronize_session=False)
db.commit()
print(f"  propagation_nodes: {deleted} rows")

print("Clearing event_opinions...")
deleted = db.query(EventOpinion).delete(synchronize_session=False)
db.commit()
print(f"  event_opinions: {deleted} rows")

print("Clearing alert_records...")
deleted = db.query(AlertRecord).delete(synchronize_session=False)
db.commit()
print(f"  alert_records: {deleted} rows")

print("Clearing events...")
deleted = db.query(Event).delete(synchronize_session=False)
db.commit()
print(f"  events: {deleted} rows")

print("Clearing opinions...")
deleted = db.query(Opinion).delete(synchronize_session=False)
db.commit()
print(f"  opinions: {deleted} rows")

print("\nAll mock data cleared. Starting fresh.")
db.close()
