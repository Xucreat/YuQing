const EVENT_STATUS_OPTIONS = [
  { value: "active", label: "关注中" },
  { value: "verifying", label: "核查中" },
  { value: "processing", label: "处理中" },
  { value: "resolved", label: "已解决" },
  { value: "closed", label: "已关闭" },
  { value: "deprecated", label: "已忽略" }
];
const EVENT_STATUS_LABELS = Object.fromEntries(
  EVENT_STATUS_OPTIONS.map((option) => [option.value, option.label])
);
function eventStatusLabel(status) {
  return status && EVENT_STATUS_LABELS[status] || status || "未知";
}
function eventStatusPill(status) {
  return {
    active: "pill-green",
    verifying: "pill-orange",
    processing: "pill-orange",
    resolved: "pill-gray",
    closed: "pill-gray",
    deprecated: "pill-gray"
  }[status || ""] || "pill-gray";
}

export { EVENT_STATUS_OPTIONS as E, eventStatusLabel as a, eventStatusPill as e };
