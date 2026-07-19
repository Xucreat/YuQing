const fs = require("fs");
const path = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js";
const src = fs.readFileSync(path, "utf8");
const lines = src.split("\n");

// Find all function declarations before line 561
for (let i = 0; i < Math.min(561, lines.length); i++) {
  const l = lines[i].trim();
  if (l.startsWith("function ") || l.startsWith("const ") || l.startsWith("let ") || l.startsWith("var ")) {
    // Show the declaration
    const name = l.match(/^\w+\s+(\w+)/);
    if (name) console.log("L" + (i+1) + ": " + (l.startsWith("function") ? "FUNC " : "DECL ") + name[1]);
  }
}
