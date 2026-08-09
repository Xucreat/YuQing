function riskColor(score) {
  if (score >= 70) return "#ff3b30";
  if (score >= 40) return "#ff9f0a";
  return "#34c759";
}
function levelPill(score) {
  if (score >= 70) return "pill-red";
  if (score >= 40) return "pill-orange";
  return "pill-green";
}
function levelText(score) {
  if (score >= 70) return "高危";
  if (score >= 40) return "中危";
  return "低危";
}
function sentimentPill(s) {
  return { negative: "pill-red", positive: "pill-green", neutral: "pill-gray" }[s] || "pill-gray";
}
function sentimentText(s) {
  return { negative: "负面", positive: "正面", neutral: "中性" }[s] || s;
}
function statusPill(s) {
  return { completed: "pill-green", failed: "pill-red", processing: "pill-orange", pending: "pill-gray" }[s] || "pill-gray";
}
function statusText(s) {
  return { completed: "已完成", failed: "失败", processing: "分析中", pending: "待分析" }[s] || s;
}
function formatTime(t) {
  if (!t) return "-";
  return t.replace("T", " ").slice(0, 19);
}

export { sentimentText as a, levelText as b, statusPill as c, statusText as d, formatTime as f, levelPill as l, riskColor as r, sentimentPill as s };
