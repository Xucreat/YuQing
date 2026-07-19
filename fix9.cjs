const fs = require('fs');
const path = 'C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js';
let s = fs.readFileSync(path, 'utf8');

s = s.replace('pns.push(")', 'pns.push("...")');
s = s.replace('p === ""', 'p === "..."');
s = s.replace('disabled>/button>', 'disabled>...</button>');

fs.writeFileSync(path, s, 'utf8');
const { execSync } = require('child_process');
try {
  execSync('node --check "' + path + '"', { encoding: 'utf8', stdio: 'pipe' });
  console.log('SYNTAX OK!');
} catch(e) {
  console.log('Remaining error:', e.stderr.split('\n')[0]);
}
