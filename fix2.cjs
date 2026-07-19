const fs = require("fs");
const dst = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js";
let s = fs.readFileSync(dst, "utf8");
let origLen = s.length;

// Fix 1: OPINIONS
const fix1 = s.match(/注意.*risk_level.*const OPINIONS = \[/);
if (fix1) {
  console.log("Fix1 match:", JSON.stringify(fix1[0]).substring(0,80));
  s = s.replace(fix1[0], fix1[0].replace("const OPINIONS = [", "\nconst OPINIONS = ["));
}

// Fix 2: TREND
const fix2 = s.match(/Dashboard.*const TREND = \[/);
if (fix2) {
  console.log("Fix2 match:", JSON.stringify(fix2[0]).substring(0,80));
  s = s.replace(fix2[0], fix2[0].replace("const TREND = [", "\nconst TREND = ["));
}

// Fix 3: KEYWORDS
const fix3 = s.match(/Dashboard 关键词.*const KEYWORDS = \[/);
if (fix3) {
  s = s.replace(fix3[0], fix3[0].replace("const KEYWORDS = [", "\nconst KEYWORDS = ["));
}

// Fix 4: loadOpinions
const fix4 = s.match(/模拟.*function loadOpinions\(\) \{/);
if (fix4) {
  s = s.replace(fix4[0], fix4[0].replace("function loadOpinions() {", "\n  function loadOpinions() {"));
}

// Fix 5: origin (in a function, the const is after a comment)
const fix5 = s.match(/留足间隙不重叠\s+const origin =/);
if (fix5) {
  s = s.replace(fix5[0], "留足间隙不重叠\n    const origin =");
}

// Fix 6: headers
const fix6 = s.match(/阶段表头.*const headers =/);
if (fix6) {
  s = s.replace(fix6[0], fix6[0].replace("const headers =", "\n    const headers ="));
}

console.log("Fixes applied:", s.length - origLen, "bytes changed");
fs.writeFileSync(dst, s, "utf8");
