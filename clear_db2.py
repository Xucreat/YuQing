import sys; sys.path.insert(0, r"C:\Users\Administrator\Desktop\YQ\backend")
from app.db.session import SessionLocal
from app.models.propagation import PropagationNode
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRecord
from app.models.event import Event
from app.models.opinion import Opinion

db = SessionLocal()

# FK-safe order
db.query(PropagationNode).update({"parent_id": None}, synchronize_session=False)
db.query(PropagationNode).delete(synchronize_session=False)
db.query(EventOpinion).delete(synchronize_session=False)
db.query(AlertRecord).delete(synchronize_session=False)
db.query(Event).delete(synchronize_session=False)
db.query(Opinion).delete(synchronize_session=False)
db.commit()
print("All tables cleared")
db.close()
