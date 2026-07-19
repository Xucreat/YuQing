import pathlib
p = pathlib.Path(r'C:\Users\Administrator\Desktop\YQ\frontend\src\views\Propagation.vue')
t = p.read_text(encoding='utf-8')
# Find the exact lines and fix them
lines = t.split('\n')
for i, line in enumerate(lines):
    if 'api.get<PropagationGraph>(' in line and '/propagation/graph/' in line:
        lines[i] = "      const { data } = await api.get<PropagationGraph>(\x60/propagation/graph/\x24{ev.event_id}\x60)"
        print(f'Fixed line {i+1}: {lines[i]}')
    if 'api.post<PropagationRebuildResponse>(' in line and '/propagation/rebuild/' in line:
        lines[i] = "      const { data } = await api.post<PropagationRebuildResponse>(\x60/propagation/rebuild/\x24{selectedEvent.value.event_id}\x60)"
        print(f'Fixed line {i+1}: {lines[i]}')
t = '\n'.join(lines)
p.write_text(t, encoding='utf-8')
print('Done')
