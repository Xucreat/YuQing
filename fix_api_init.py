import pathlib

p = pathlib.Path(r'C:\Users\Administrator\Desktop\YQ\backend\app\api\__init__.py')
t = p.read_text(encoding='utf-8')

if 'from app.api.alerts import alerts_router' not in t:
    t = t.replace(
        'from app.api.events import events_router',
        'from app.api.alerts import alerts_router\nfrom app.api.events import events_router\nfrom app.api.propagation import propagation_router'
    )
if 'api_router.include_router(alerts_router' not in t:
    t = t.replace(
        'api_router.include_router(events_router, prefix="/events")',
        'api_router.include_router(alerts_router, prefix="/alerts")\napi_router.include_router(events_router, prefix="/events")\napi_router.include_router(propagation_router, prefix="/propagation")'
    )

p.write_text(t, encoding='utf-8')
print('API __init__.py updated')
