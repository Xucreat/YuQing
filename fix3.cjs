const fs = require("fs");
const path = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js";
const { execSync } = require("child_process");

function checkSyntax() {
  try {
    execSync('node --check "' + path + '"', { encoding: "utf8", stdio: "pipe" });
    return { ok: true, error: null };
  } catch (e) {
    const lines = e.stderr.split("\n");
    const errorLine = lines.find(l => l.includes("SyntaxError:"));
    const lineMatch = e.stderr.match(/(\d+):(\d+)/);
    return { ok: false, error: errorLine || e.stderr.substring(0, 200), line: lineMatch ? parseInt(lineMatch[1]) : null };
  }
}

let s = fs.readFileSync(path, "utf8");
let origLen = s.length;

// Fix 1: Broken array values like ["red", "] -> ["red", ""]
s = s.replace(/\[\s*"[^"]*"\s*,\s*"\s*\]/g, m => {
  // Close the string before ]
  const parts = m.split(",");
  // parts[1] is something like ' "'
  return parts[0] + ', ""';
});

// Fix 2: Handle missing closing " before ] in general
s = s.replace(/,\s*"(\s*)\]/g, (m, spaces) => ', ""' + spaces + ']');

// Write and check
fs.writeFileSync(path, s, "utf8");
console.log("Applied auto-fixes. Bytes changed:", s.length - origLen);
const result = checkSyntax();
console.log("Syntax OK:", result.ok);
if (!result.ok) console.log("Error:", result.error, "at line", result.line);
