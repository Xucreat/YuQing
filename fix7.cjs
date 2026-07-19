const fs = require('fs');
const path = 'C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js';
let s = fs.readFileSync(path, 'utf8');

// Fix 9: broken string
s = s.replace('pns.push(\")', 'pns.push(\"...\")');

// Fix 10: origin
s = s.replace('名与数留足间隙不重    const origin =', '名与数留足间隙不重叠\n    const origin =');

// Fix 11: location.hash
s = s.replace('return; // 链接已处        location.hash =', 'return; // 链接已处理\n        location.hash =');

// Fix 12: auth guard if
s = s.replace('// 鉴权守卫（对frontend router beforeEach    if (!token && hash !== \"#/login\") {', '// 鉴权守卫（对应frontend router beforeEach）\n    if (!token && hash !== \"#/login\") {');

// Fix 13: splash if
s = s.replace('// 首屏：无 hash 时给个默认  if (!location.hash) location.hash = \"#/dashboard\";', '// 首屏：无 hash 时给个默认值\n  if (!location.hash) location.hash = \"#/dashboard\";');

fs.writeFileSync(path, s, 'utf8');
console.log('Applied. Size:', s.length);

const { execSync } = require('child_process');
try {
  execSync('node --check "' + path + '"', { encoding: 'utf8', stdio: 'pipe' });
  console.log('SYNTAX OK!');
} catch(e) {
  console.log('Error:', e.stderr.split('\n')[0]);
}
