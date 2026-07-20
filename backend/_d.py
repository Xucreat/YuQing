import subprocess, pathlib
script = 'const fs=require("fs");const path=require("path");function walk(d){const e=fs.readdirSync(d,{withFileTypes:true});for(const de of e){const p=path.join(d,de.name);const rp=path.relative("dist",p).split(path.sep).join("/");if(de.isDirectory())walk(p);else{const c=fs.readFileSync(p);const nb=Buffer.from(rp,"utf8");const h=Buffer.alloc(8);h.writeUInt32LE(nb.length,0);h.writeUInt32LE(c.length,4);process.stdout.write(h);process.stdout.write(nb);process.stdout.write(c)}}}walk("dist")'
r = subprocess.run(["node","-e",script], capture_output=True, cwd=r"C:/Users/Administrator/Desktop/YQ/frontend")
target = pathlib.Path(r"C:/Users/Administrator/Desktop/YQ/backend/app/static")
target.mkdir(parents=True, exist_ok=True)
data, off, count = r.stdout, 0, 0
while off+8 <= len(data):
    pl = int.from_bytes(data[off:off+4],"little"); off += 4
    cl = int.from_bytes(data[off:off+4],"little"); off += 4
    if off+pl+cl > len(data): break
    fn = data[off:off+pl].decode("utf-8"); off += pl
    fp = target / fn; fp.parent.mkdir(parents=True, exist_ok=True); fp.write_bytes(data[off:off+cl]); off += cl; count += 1
print(f"Wrote {count} files")
print(f"index.html exists: {(target/'index.html').exists()}")
