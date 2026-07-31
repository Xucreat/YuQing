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
const EVENT_TOPIC_LABELS = {
  livelihood: "民生",
  traffic: "交通",
  education: "教育",
  healthcare: "医疗卫生",
  environment: "环境",
  safety: "安全",
  market: "市场",
  gov_service: "政务服务",
  social_security: "社会保障",
  public_emergency: "公共突发事件",
  other: "其他"
};
function topicValueFromLabel(label) {
  const entry = Object.entries(EVENT_TOPIC_LABELS).find(([, l]) => l === label);
  return entry ? entry[0] : label;
}

export { EVENT_STATUS_OPTIONS as E, eventStatusLabel as a, eventStatusPill as e, topicValueFromLabel as t };
