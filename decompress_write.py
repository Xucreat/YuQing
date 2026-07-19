import sys, os

ROOT = r'C:\Users\Administrator\Desktop\YQ\frontend\node_modules_decompressed'
data = sys.stdin.buffer.read()
n = len(data)
i = 0
written = 0
while i < n:
    plen = int.from_bytes(data[i:i+4], 'little'); i += 4
    clen = int.from_bytes(data[i:i+4], 'little'); i += 4
    p = data[i:i+plen].decode('utf-8'); i += plen
    content = data[i:i+clen]; i += clen
    fp = os.path.join(ROOT, p)
    d = os.path.dirname(fp)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(fp, 'wb') as f:
        f.write(content)
    written += 1

sys.stderr.write('\n[decompress_write] wrote %d files, %d bytes\n' % (written, n))
print('OK', written, n)
