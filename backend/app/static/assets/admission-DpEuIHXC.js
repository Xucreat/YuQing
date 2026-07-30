function formatAdmissionHit(hit) {
  if (typeof hit === "string" || typeof hit === "number") return String(hit);
  if (!hit || typeof hit !== "object" || Array.isArray(hit)) return "";
  const value = hit;
  for (const key of ["word", "name", "label", "value", "code"]) {
    const candidate = value[key];
    if (typeof candidate === "string" || typeof candidate === "number") return String(candidate);
  }
  return "";
}
function formatAdmissionHits(value, limit) {
  if (!Array.isArray(value)) return "";
  return value.map(formatAdmissionHit).filter(Boolean).slice(0, limit).join("、");
}

export { formatAdmissionHits as f };
