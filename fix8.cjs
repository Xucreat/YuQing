const fs = require('fs');
const path = 'C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js';
let s = fs.readFileSync(path, 'utf8');

// Fix push(") patterns - add closing quote
s = s.replace(/pns\.push\("\)/g, 'pns.push("...")');
// Fix p === "" patterns  
s = s.replace(/p === ""/g, 'p === "..."');
// Fix missing < in </button>
s = s.replace(/disabled>/button>/g, 'disabled>...</button>');

fs.writeFileSync(path, s, 'utf8');
console.log('Fixed. Size:', s.length);

const { execSync } = require('child_process');
try {
  execSync('node --check "' + path + '"', { encoding: 'utf8', stdio: 'pipe' });
  console.log('SYNTAX OK!');
} catch(e) {
  console.log('Error:', e.stderr.split('\n')[0]);
}
