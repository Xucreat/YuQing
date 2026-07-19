const fs = require("fs");
const path = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js";
let s = fs.readFileSync(path, "utf8");

// Fix 8: if swallowed by comment in login handler
const fix8 = s.match(/模拟 POST \/api\/login（真实仅校验 admin\/admin123\s+if \(u === "admin" && p === "admin123"\) \{/);
if (fix8) {
  console.log("Fix 8: matched");
  s = s.replace(fix8[0], "模拟 POST /api/login（真实仅校验 admin/admin123）\n      if (u === \"admin\" && p === \"admin123\") {");
}

// Also check for other comment-swallowed declarations
// Find any '//' line that contains 'function ' or 'const ' or 'if ' after it
const lines = s.split("\n");
for (let i = 0; i < lines.length; i++) {
  const l = lines[i];
  // Check if a // comment line contains a declaration at the end
  if (l.includes("//") && (l.includes("const ") || l.includes("function ") || l.includes("if ("))) {
    // This might be a swallowed declaration
    console.log("Potential swallowed declaration at L" + (i+1) + ": " + JSON.stringify(l.trim()).substring(0, 80));
  }
}

fs.writeFileSync(path, s, "utf8");

const { execSync } = require("child_process");
try {
  execSync("node --check \"" + path + "\"", { encoding: "utf8", stdio: "pipe" });
  console.log("SYNTAX OK!");
} catch (e) {
  console.log("Syntax error:", e.stderr.split("\n")[0]);
}
