const fs = require("fs");
const path = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js";
const src = fs.readFileSync(path, "utf8");
const lines = src.split("\n");

// Track string/comment state per character
let state = { inBlock: false, inLine: false, inString: false, inBacktick: false, inRegex: false, stringStart: -1, stringLine: -1 };

for (let i = 0; i < src.length; i++) {
  const c = src[i];
  const n = src[i+1] || "";
  const p = src[i-1] || "";
  
  if (state.inBlock) {
    if (c === "*" && n === "/") { state.inBlock = false; i++; }
    continue;
  }
  if (state.inLine) {
    if (c === "\n") { state.inLine = false; }
    continue;
  }
  
  if (c === "/" && n === "*") { state.inBlock = true; i++; continue; }
  if (c === "/" && n === "/") { state.inLine = true; i++; continue; }
  
  if (state.inString) {
    if (c === '"' && p !== "\\") { state.inString = false; }
    continue;
  }
  if (state.inBacktick) {
    if (c === "`" && p !== "\\") { state.inBacktick = false; }
    continue;
  }
  
  if (c === '"' && !state.inString && !state.inBacktick) {
    state.inString = true;
    continue;
  }
  if (c === "`" && !state.inString && !state.inBacktick) {
    state.inBacktick = true;
    continue;
  }
}

const lastNewline = src.lastIndexOf("\n");
const lastLine = src.substring(lastNewline + 1).trim();
console.log("State at EOF:");
console.log("  inBlock:", state.inBlock);
console.log("  inLine:", state.inLine);  
console.log("  inString:", state.inString);
console.log("  inBacktick:", state.inBacktick);
console.log("  last few lines:", lastLine.substring(0,80));
