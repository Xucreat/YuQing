import pathlib
al = pathlib.Path(r'C:/Users/Administrator/Desktop/YQ/frontend/src/components/AppLayout.vue')
raw = al.read_bytes()
# original length
orig_len = len(raw)
print(f'Original: {orig_len} bytes')

# Find marker: brand-name">\r\n          
marker = bytes([98,114,97,110,100,45,110,97,109,101,34,62,13,10]) + b'          '
idx = raw.find(marker)
start = idx + len(marker)

# Find </small>  using explicit bytes
end_tag = bytes([60,47,115,109,97,108,108,62])
end = raw.find(end_tag, start)
print(f'start={start}, end_tag at {end}')

# Correct brand text (Chinese + small tag)
correct = '\u8206\u60c5\u76d1\u6d4b\u7814\u5224\u5e73\u53f0\r\n          \u003csmall\u003e\u5927\u5382\u53bf\u516c\u5b89'.encode('utf-8')

# Reconstruct: everything before start + correct text + from </small> onwards
new_raw = raw[:start] + correct + raw[end:]
al.write_bytes(new_raw)
new_len = len(new_raw)
print(f'New: {new_len} bytes')

v = al.read_text('utf-8')
lines = v.split('\n')
print(f'Lines: {len(lines)}')
print('First 8:')
for i in range(min(8, len(lines))):
    print(f'  {i+1}: {lines[i][:80]}')