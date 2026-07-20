import subprocess, pathlib
script = 'const fs=require(\"fs\");const path=require(\"path\");function walk(d,b){const e=fs.readdirSync(d,{withFileTypes:true});for(const de of e){const p=path.join(d,de.name);const rp=path.relative(\"dist\",p).split(path.sep).join(\"/\");if(de.isDirectory()) walk(p,null);else {const c=fs.readFileSync(p);const nb=Buffer.from(rp,\"utf8\");const head=Buffer.alloc(8);head.writeUInt32LE(nb.length,0);head.writeUInt32LE(c.length,4);process.stdout.write(head);process.stdout.write(nb);process.stdout.write(c)}}};walk(\"dist\",null)'
r = subprocess.run([\"node\",\"-e\",script], capture_output=True, cwd=r\"C:\Users\Administrator\Desktop\YQ\frontend\")
target = pathlib.Path(r\"C:\Users\Administrator\Desktop\YQ\backend\app\static\")
target.mkdir(parents=True, exist_ok=True)
data, off, count = r.stdout, 0, 0
while off+8 <= len(data):
    pl = int.from_bytes(data[off:off+4],\"little\")
    cl = int.from_bytes(data[off+4:off+8],\"little\")
    off += 8
    if off+pl+cl > len(data): break
    fn = data[off:off+pl].decode(\"utf-8\")
    off += pl
    fp = target / fn
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_bytes(data[off:off+cl])
    off += cl
    count += 1
print(f\"Wrote {count} files\")
print(f\"index.html: {(target/'index.html').exists()}\")