// Stream every file in node_modules (decompressed view that only node sees)
// to stdout as frames: [4B pathLen][4B contentLen][pathUtf8][content].
// A non-node writer (python) re-materializes them as plain on-disk files,
// bypassing the node-write -> compress filter driver on this machine.
const fs = require('fs');
const path = require('path');

const root = path.resolve('node_modules');
const out = process.stdout;
const skipDirs = new Set(['.vite', '.bin', '.cache', '.git']);

let count = 0;
let bytes = 0;

function rel(p) {
  return path.relative(root, p).split(path.sep).join('/');
}

function emit(p) {
  let b;
  try {
    b = fs.readFileSync(p); // node view = decompressed
  } catch (e) {
    return;
  }
  if (b.length > 0x7fffffff) return;
  if (b.length === 0) return;
  const pb = Buffer.from(rel(p), 'utf8');
  const head = Buffer.alloc(8);
  head.writeUInt32LE(pb.length, 0);
  head.writeUInt32LE(b.length, 4);
  out.write(head);
  out.write(pb);
  out.write(b);
  count++;
  bytes += b.length;
}

function walk(d, writeBase) {
  let entries;
  try {
    entries = fs.readdirSync(d, { withFileTypes: true });
  } catch (e) {
    return;
  }
  for (const e of entries) {
    const p = path.join(d, e.name);
    const wb = path.join(writeBase, e.name);
    try {
      if (e.isSymbolicLink()) {
        let rp;
        try { rp = fs.realpathSync(p); } catch (_) { continue; }
        let st;
        try { st = fs.lstatSync(rp); } catch (_) { continue; }
        if (st.isDirectory()) walk(rp, wb);
        else emit(wb);
      } else if (e.isDirectory()) {
        if (skipDirs.has(e.name)) continue;
        walk(p, p);
      } else if (e.isFile()) {
        emit(wb);
      }
    } catch (_) {
      // ignore individual errors, keep going
    }
  }
}

walk(root, root);
process.stderr.write('\n[decompress_deps] scanned ' + count + ' files, ' + bytes + ' bytes\n');
