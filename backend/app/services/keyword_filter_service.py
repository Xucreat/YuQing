"""Phase X：关键词专项语义过滤服务（轻量规则，零 AI、零新依赖）。

仅对特定「地域实体关键词」（当前：keyword == "大厂"，特指河北省廊坊市
大厂回族自治县）生效；其余所有关键词（27 个地域词 + 14 个主题词）行为完全不变。

设计要点：
- 默认拒绝 + 分级放行（黑名单不可穷举：PCB大厂/面板大厂/存储大厂…）。
- 本地源豁免：source scope 绑定廊坊辖区 → 内容天然本地，不参与判定。
- 邻接窗口判定（前后各 6 字），不用全文 contains，避免「走进大厂」类误伤。
- 规则以「代码内置默认 + keywords.rule_config 镜像」双轨存在：
  - 运行时使用内置 DEFAULT_RULE（与 id=30 的 rule_config 完全一致），
    避免迁移 / 播种时序耦合（用户确认保留代码默认 fallback）。
  - keywords.rule_config 为可维护镜像，供未来 UI / 运维调整关键词规则。

判定层级（自上而下，首个命中即返回）：
  L0 本地源豁免
    → L1 强地域锚点（大厂回族自治县 / 大厂县 / 大厂镇 / 廊坊大厂 / 大厂支行 …）
    → L2 邻接窗口负向（前 6 字前缀 / 后 6 字后缀）
    → L2b 全文职场 / 行业语境词
    → L3 上位地名共现（廊坊 / 潮白河 / 三河市 …）
    → L4 政务标题地名领起模式 + 政务语义
    → L5 民生诉求兜底（居民 / 群众 / 反映 / 道路 …，宁收不漏）
    → L6 孤立锚点兜底过滤
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# 内置默认规则（与 keywords(id=30).rule_config 镜像一致；运行时权威来源）。
# 修改规则请同步更新 DB 中 id=30 的 rule_config（见实施报告播种脚本）。
# ---------------------------------------------------------------------------
DEFAULT_RULE: Dict[str, object] = {
    "version": 1,
    "anchor": "大厂",
    "strategy": "default_reject_then_allow",
    "strong_geo": [
        "大厂回族自治县", "大厂回族", "大厂县", "大厂镇", "廊坊大厂", "大厂高新",
        "大厂开发区", "大厂民族宫", "大厂潮白河", "大厂牛肉", "走进大厂", "大厂分局",
        "大厂支行", "大厂公安", "大厂交警", "大厂消防", "大厂法院", "大厂检察院",
        "大厂纪委", "大厂政府", "大厂县委", "大厂县政府", "大厂教育局", "大厂人社",
        "大厂文广旅", "大厂医院", "大厂一中", "大厂卫健", "大厂市场监管",
        "大厂应急管理", "大厂生态环境", "大厂住建",
    ],
    "upper_geo": [
        "廊坊", "北三县", "潮白河", "河北省廊坊", "三河市", "香河县", "固安县",
        "永清县", "文安县", "大城县", "霸州市", "安次区", "广阳区",
    ],
    "neg_prefix": [
        "互联网", "科技", "企业", "AI", "ai", "PCB", "pcb", "面板", "存储", "芯片",
        "半导体", "手机", "数码", "国际", "国内", "海外", "游戏", "元器件", "各大",
        "知名", "头部", "巨头", "厂商", "电池", "家电", "汽车", "光伏", "面粉",
        "外资", "日系", "韩系",
    ],
    "neg_suffix": [
        "员工", "程序员", "offer", "Offer", "OFFER", "裁员", "招聘", "薪资", "跳槽",
        "经验", "面试", "实习", "内推", "福利", "加班", "人", "公务员", "CTO",
        "高管", "打工", "商", "财报", "停产", "抢人", "角逐", "暗战", "各寻", "齐聚",
        "扎堆", "集体", "示警", "警告", "光环", "背景", "待遇", "开始", "挤爆",
        "烧钱", "执行", "专家", "足球", "的“城”", "新秀", "选出", "首位", "这个词",
        "抢滩", "入局",
    ],
    "gov_lead_patterns": [r"大厂[:：]", r"——大厂", r"—大厂", r"\|大厂", r"】大厂"],
    "gov_semantic": [
        "全力筑牢", "以科技联动", "品牌建设", "和美乡村", "加速崛起", "打通", "召开",
        "举办", "开展", "推进", "书记", "县长", "县委", "全会", "防汛", "创城",
    ],
    "neg_context": [
        "程序员", "互联网", "裁员", "offer", "跳槽", "面试", "内推", "实习生", "薪资",
        "职场", "求职", "校招", "社招", "加班", "996", "KPI", "期权", "年终奖",
        "涨薪", "算力", "大模型", "AI Agent", "芯片", "半导体", "存储", "DRAM",
        "HBM", "PCB", "阿里", "腾讯", "字节跳动", "京东", "美团", "百度", "网易",
        "华为", "小米", "赛道", "融资轮", "IPO", "财报", "股价", "涨价", "供应商",
        "产业链", "赛马",
    ],
    "livelihood": [
        "居民", "群众", "村民", "业主", "家长", "反映", "投诉", "举报", "维权",
        "求助", "停水", "停电", "供暖", "燃气", "物业", "小区", "道路", "污染",
        "欠薪", "拖欠", "事故", "火灾", "爆炸", "坍塌", "伤亡", "食品安全", "医保",
        "社保", "拆迁", "征地",
    ],
}

# 受本服务治理的关键词集合（当前仅「大厂」）。其余关键词一律视为「不介入」。
FLAGGED_KEYWORDS = frozenset({"大厂"})

_WINDOW = 6  # 邻接窗口：前后各 6 字


class KeywordFilterService:
    """关键词专项语义过滤。

    is_valid_match(keyword, text, *, is_local_source=False) -> bool
      - keyword 不在 FLAGGED_KEYWORDS 中 → 恒返回 True（完全不影响其他关键词）。
      - keyword == "大厂"：按 L0–L6 规则判定，返回是否「保留进入舆情库」。
    """

    _default_instance: "Optional[KeywordFilterService]" = None

    def __init__(self, rule: Optional[Dict[str, object]] = None) -> None:
        self.rule = dict(DEFAULT_RULE if rule is None else rule)
        self.anchor: str = str(self.rule.get("anchor", "大厂"))
        self.strong_geo: List[str] = list(self.rule.get("strong_geo", DEFAULT_RULE["strong_geo"]))
        self.upper_geo: List[str] = list(self.rule.get("upper_geo", DEFAULT_RULE["upper_geo"]))
        self.neg_prefix: List[str] = list(self.rule.get("neg_prefix", DEFAULT_RULE["neg_prefix"]))
        self.neg_suffix: List[str] = list(self.rule.get("neg_suffix", DEFAULT_RULE["neg_suffix"]))
        self.gov_lead_patterns: List[str] = list(
            self.rule.get("gov_lead_patterns", DEFAULT_RULE["gov_lead_patterns"])
        )
        self.gov_semantic: List[str] = list(self.rule.get("gov_semantic", DEFAULT_RULE["gov_semantic"]))
        self.neg_context: List[str] = list(self.rule.get("neg_context", DEFAULT_RULE["neg_context"]))
        self.livelihood: List[str] = list(self.rule.get("livelihood", DEFAULT_RULE["livelihood"]))

    @classmethod
    def default(cls) -> "KeywordFilterService":
        """进程级单例：运行时使用内置默认规则，无需每次构造。"""
        if cls._default_instance is None:
            cls._default_instance = KeywordFilterService()
        return cls._default_instance

    @classmethod
    def from_rule_config(cls, config_json) -> "KeywordFilterService":
        """从 keywords.rule_config(JSON) 构造（供未来 DB 驱动；缺字段回退默认）。"""
        if not config_json:
            return cls.default()
        rule = dict(DEFAULT_RULE)
        for k in (
            "strong_geo", "upper_geo", "neg_prefix", "neg_suffix",
            "gov_lead_patterns", "gov_semantic", "neg_context", "livelihood",
        ):
            if isinstance(config_json.get(k), list):
                rule[k] = config_json[k]
        if config_json.get("anchor"):
            rule["anchor"] = config_json["anchor"]
        return cls(rule)

    def is_valid_match(self, keyword: str, text: str, *, is_local_source: bool = False) -> bool:
        """判定某关键词命中是否构成有效的「地域语义命中」。

        - keyword 非本服务治理对象 → 返回 True（原逻辑不变）。
        - 文本不含 anchor → 返回 True（规则不介入）。
        - 本地源 → 返回 True（L0 豁免）。
        - 否则按 L1–L6 判定。
        """
        if keyword not in FLAGGED_KEYWORDS:
            return True
        if not text or self.anchor not in text:
            return True
        return self._decide(text, is_local_source=is_local_source)

    def _decide(self, text: str, *, is_local_source: bool) -> bool:
        txt = text or ""

        # L0 本地源豁免
        if is_local_source:
            return True

        # L1 强地域锚点
        for w in self.strong_geo:
            if w in txt:
                return True

        # L2 邻接窗口负向（前 6 字 / 后 6 字）
        for m in re.finditer(re.escape(self.anchor), txt):
            before = txt[max(0, m.start() - _WINDOW):m.start()]
            after = txt[m.end():m.end() + _WINDOW]
            for p in self.neg_prefix:
                if before.endswith(p):
                    return False
            for s in self.neg_suffix:
                if after.startswith(s):
                    return False

        # L2b 全文职场 / 行业语境词
        for w in self.neg_context:
            if w in txt:
                return False

        # L3 上位地名共现
        for w in self.upper_geo:
            if w in txt:
                return True

        # L4 政务标题地名领起 + 政务语义
        for pat in self.gov_lead_patterns:
            if re.search(pat, txt):
                if any(g in txt for g in self.gov_semantic):
                    return True

        # L5 民生诉求兜底（宁收不漏）
        for w in self.livelihood:
            if w in txt:
                return True

        # L6 孤立锚点兜底过滤
        return False
