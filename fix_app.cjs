const fs = require("fs");
const src = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app_full.txt";
const dst = "C:/Users/Administrator/Desktop/YQ/prototype/apple-style/app.js";
let s = fs.readFileSync(src, "utf8");

// Fix comment-swallowed declarations
const fixes = [
  ["注意：risk_level 在真实系统中实际映射sentiment（positive/negative/neutral）  const OPINIONS = [", "注意：risk_level 在真实系统中实际映射sentiment（positive/negative/neutral）\nconst OPINIONS = ["],
  ["Dashboard 趋势：对DashboardStatsResponse.trend（最近日，无数据日补0）  const TREND = [", "Dashboard 趋势：对齐DashboardStatsResponse.trend（最近7日，无数据日补0）\nconst TREND = ["],
  ["Dashboard 关键词：对齐 DashboardStatsResponse.keywords（TOP，逗号拆分统计）  const KEYWORDS = [", "Dashboard 关键词：对齐 DashboardStatsResponse.keywords（TOP，逗号拆分统计）\nconst KEYWORDS = ["],
  ["模拟「写库」：localStorage 覆盖原始模拟数据，刷新后仍保  function loadOpinions() {", "模拟「写库」：localStorage 覆盖原始模拟数据，刷新后仍保持\n  function loadOpinions() {"],
  ["留足间隙不重    const origin =", "留足间隙不重叠\n    const origin ="],
  ["阶段表头（明从左到右的叙事逻辑）    const headers =", "阶段表头（明从左到右的叙事逻辑）\n    const headers ="]
];
for (const [from, to] of fixes) {
  if (s.includes(from)) {
    s = s.replace(from, to);
    console.log("Fixed:", from.substring(0, 30) + "...");
  }
}

// Regex fixes for replacement characters
// First: \\ufffd? followed by specific punctuation -> " (closing quote)
s = s.replace(/\ufffd\?(\s*[,;\r\n\]\}])/g, (m, p1) => '"' + p1);
// Next: \\ufffd? followed by " -> remove \\ufffd? (keep the closing quote)
s = s.replace(/\ufffd\?"/g, '"');
// Finally: remove any remaining \\ufffd? or \\ufffd
s = s.replace(/\ufffd\?/g, "");
s = s.replace(/\ufffd/g, "");

fs.writeFileSync(dst, s, "utf8");
console.log("Done. File size:", s.length);
