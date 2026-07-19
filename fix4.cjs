const fs = require("fs");
const path = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js";
let s = fs.readFileSync(path, "utf8");

// Fix 7: propagationNetworkSVG swallowed by comment
const fix7 = s.match(/图文挤\s+function propagationNetworkSVG\(platforms, nodes\) \{/);
if (fix7) {
  console.log("Fix 7 match:", JSON.stringify(fix7[0]).substring(0, 60));
  s = s.replace(fix7[0], "图文拥挤\nfunction propagationNetworkSVG(platforms, nodes) {");
}

fs.writeFileSync(path, s, "utf8");

// Check syntax
const { execSync } = require("child_process");
try {
  execSync("node --check \"" + path + "\"", { encoding: "utf8", stdio: "pipe" });
  console.log("SYNTAX OK!");
} catch (e) {
  console.log("Syntax error:", e.stderr.split("\n")[0]);
}
