import pathlib

p = pathlib.Path(r'C:\Users\Administrator\Desktop\YQ\backend\app\models\alert.py')
t = p.read_text(encoding='utf-8')
t = t.replace('IN (low,medium,high,critical)', 'IN (\x27low\x27,\x27medium\x27,\x27high\x27,\x27critical\x27)')
p.write_text(t, encoding='utf-8')
print('alert.py fixed')

p2 = pathlib.Path(r'C:\Users\Administrator\Desktop\YQ\backend\app\models\__init__.py')
t2 = p2.read_text(encoding='utf-8')
t2 = t2.replace(
    'from app.models.event_opinion import EventOpinion',
    'from app.models.event_opinion import EventOpinion\nfrom app.models.alert import AlertRule, AlertRecord\nfrom app.models.propagation import PropagationNode'
)
t2 = t2.replace(
    '"EventOpinion",',
    '"EventOpinion",\n    "AlertRule",\n    "AlertRecord",\n    "PropagationNode",'
)
p2.write_text(t2, encoding='utf-8')
print('__init__ updated')
