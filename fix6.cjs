const fs = require("fs");
const path = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js";
let s = fs.readFileSync(path, "utf8");

// Fix 9: broken string pns.push(")
s = s.replace(/pns\.push\("\)/g, "pns.push(\"…\")");

// Fix 10: origin swallowed (line 500-ish)
s = s.replace(/(\bconst top = 96, bottom = H - 44;.*)名[与和]\S+留足间隙不重\s+(\bconst origin =)/, 
  "$1名与数值留足间隙不重叠\n    $2");

// Fix 11: location.hash swallowed by comment (line 848)
s = s.replace(
  /if \(e\.target\.tagName === "A"\) return; \/\/ 链接已处\s+location\.hash = "#\\/opinion\\/" \+ tr\.getAttribute\("data-id"\);/,
  "if (e.target.tagName === \"A\") return; // 链接已处理\n        location.hash = \"#/opinion/\" + tr.getAttribute(\"data-id\");"
);

// Fix 12: if swallowed by comment (line 1271)
s = s.replace(
  /\/\/ 鉴权守卫（对frontend router beforeEach\s+if \(!token && hash !== "#\\/login"\) \{/,
  "// 鉴权守卫（对应frontend router beforeEach）\n    if (!token && hash !== \"#/login\") {"
);

// Fix 13: if swallowed (line 1288)
s = s.replace(
  /\/\/ 首屏：无 hash 时给个默认\s+if \(!location\.hash\) location\.hash = "#\\/dashboard";/,
  "// 首屏：无 hash 时给个默认值\n  if (!location.hash) location.hash = \"#/dashboard\";"
);

fs.writeFileSync(path, s, "utf8");
console.log("All remaining fixes applied");

const { execSync } = require("child_process");
try {
  execSync("node --check \"" + path + "\"", { encoding: "utf8", stdio: "pipe" });
  console.log("SYNTAX OK!");
} catch (e) {
  console.log("Syntax error:", e.stderr.split("\n")[0]);
}
