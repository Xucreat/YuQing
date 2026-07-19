const fs = require('fs');
const p = 'C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js';
let s = fs.readFileSync(p, 'utf8');
s = s.replace('需重点跟进 :', '需重点跟进" :');
s = fs.readFileSync(p, 'utf8');
s = s.replace('风险相对可控);', '风险相对可控");');
fs.writeFileSync(p, s, 'utf8');
console.log('Fixed L951');
const { execSync } = require('child_process');
try {
  execSync('node --check "' + p + '"', { encoding: 'utf8', stdio: 'pipe' });
  console.log('SYNTAX OK!');
} catch(e) {
  console.log('Next error:', e.stderr.split('\n')[0]);
}
