# 大厂关键词地域语义过滤 — Phase X-2 实施报告

> 范围：仅治理「大厂」关键词的新增数据入口（L0–L6 语义过滤）。
> 历史 73 条噪声数据**不清理、不修改**（另立 Phase X-History）。
> 关键词管理 UI **不暴露** rule_config 编辑入口（由后端治理维护）。

---

## 1. 实施概览

| 项 | 结果 |
|---|---|
| 代码依赖 | 零新增第三方依赖；未引入任何 AI/大模型 |
| 其他关键词行为 | 完全不变（仅 `keyword=="大厂"` 介入） |
| 数据库变更 | `keywords` 表新增 `rule_config` JSONB 可空列（迁移 `p27`） |
| 历史数据 | 未删除、未修改任何 opinion 行 |
| 回归测试 | 25/25 通过（含生产库 122 条历史回放） |

---

## 2. 变更文件清单（8 项）

| # | 文件 | 类型 | 用途 |
|---|---|---|---|
| 1 | `backend/app/services/keyword_filter_service.py` | **新增** | `KeywordFilterService` + 内置 `DEFAULT_RULE` + `FLAGGED_KEYWORDS={"大厂"}`；`is_valid_match(keyword, text, *, is_local_source)` 仅对大厂生效；`default()` / `from_rule_config()` 双构造入口 |
| 2 | `backend/app/models/keyword.py` | 修改 | `Keyword` 模型新增 `rule_config` 字段（`JSONB` nullable） |
| 3 | `backend/alembic/versions/p27_keyword_rule_config.py` | **新增** | 迁移 `add_column keywords.rule_config`（down_revision=`p26_report_records`） |
| 4 | `backend/app/services/keyword_service.py` | 修改 | 新增 `get_keyword_rules(db)`（60s TTL 缓存，返回 `{word: rule_config}`）；`clear_keyword_cache()` 同步失效 `_RULE_CACHE` |
| 5 | `backend/app/collectors/service.py` | 修改 | 采集主流程注入过滤：新增 `dachang_filtered` 计数、`_build_dachang_filter(db)`（**DB 优先→代码 fallback**）、`_process_collector` 内 **作用点 1 收口**（`大厂` 语义不命中→`continue` 不入库）、顺序/并发两路结果合并 |
| 6 | `backend/app/services/opinion_region_service.py` | 修改 | `_region_hits` 内 **作用点 3 防御**：裸别名 `"大厂"→131028` 经 `is_valid_match` 过滤；强锚点（大厂县/大厂回族自治县）免过滤 |
| 7 | `backend/tests/test_keyword_filter_dachang.py` | **新增** | 25 个用例（见 §4） |
| 8 | 生产库 `keywords(id=30)` | **数据** | 写入 `rule_config` JSON（与 `DEFAULT_RULE` 一致）；其余关键词恒 `NULL` |

> 注：`collectors/common.py`（`matches_region_topic`/`matches_keywords`）**未改动**，原有匹配逻辑与测试零回归。

---

## 3. 过滤规则设计（与审计报告一致，已回测 100%/100%）

默认拒绝 + 分级放行（黑名单不可穷举：PCB大厂/面板大厂/存储大厂…）：

| 层级 | 规则 | 命中即 |
|---|---|---|
| L0 | 本地源（scope 绑定廊坊辖区）豁免 | **放行** |
| L1 | 强地域锚点（大厂回族自治县/大厂县/大厂镇/廊坊大厂/大厂支行/大厂公安…） | **放行** |
| L2 | 邻接窗口（前后各 6 字）负向前缀（互联网/科技/PCB…）/后缀（员工/程序员/offer/裁员…） | **过滤** |
| L2b | 全文职场/行业语境词（程序员/互联网/裁员/阿里/腾讯/芯片/大模型…） | **过滤** |
| L3 | 上位地名共现（廊坊/潮白河/三河市/北三县…） | **放行** |
| L4 | 政务标题地名领起模式（`大厂：`/`——大厂`/`｜大厂`） + 政务语义词 | **放行** |
| L5 | 民生诉求兜底（居民/群众/反映/道路/停水…，**宁收不漏**） | **放行** |
| L6 | 孤立锚点（无任何地域证据） | **过滤** |

**关键修正（相对原始需求词表）**：
- 负向词去掉「大厂工作」（会误杀政务稿 `#1609`）、「大厂街道」改为强锚点并排除南京（避免南京大厂街道误召回 `#1710`）；
- 子串负向改为 **邻接窗口** 判定，避免「走进大厂」类政府站导航误伤（20 条本地源中 13 条原会被误杀）；
- 发现百度新闻只采标题（content==title，30–70 字），原需求「按上下文长度判断」不可行，改用 L4 政务领起模式救回 9 条纯标题真政务。

---

## 4. 验收与回归测试结果

运行：`pytest tests/test_keyword_filter_dachang.py -q` → **25 passed**

### 4.1 用户验收用例（5/5）
| 输入 | 期望 | 结果 |
|---|---|---|
| 廊坊大厂召开安全会议 | 命中 | ✅ |
| 大厂回族自治县发布公告 | 命中 | ✅ |
| 互联网大厂裁员消息 | 过滤 | ✅ |
| 程序员进入大厂工作 | 过滤 | ✅ |
| 大厂附近居民反映道路问题 | 保留 | ✅ |

### 4.2 高危边界用例（12/12）
大厂镇防汛、南京大厂街道、各大厂商、大厂公务员、政府导航「走进大厂」、大厂支行、**破折号领起**、大厂足球、本地源豁免、大厂员工、PCB大厂、天气预报列举 —— 全部正确。

### 4.3 核心回归（非大厂关键词零影响）
- 27 地域词 + 14 主题词 在 `is_valid_match` 下**恒返回 True**（互联网语境也不被误杀）。
- `matches_region_topic` / `matches_keywords` 行为不变（`common.py` 未改）。

### 4.4 历史数据回放（生产库 122 条）
`test_backtest_regression_against_history` 直连生产库（127.0.0.1:5432，只读 SELECT，
`connect_timeout=5`，不可达自动 skip），对 Phase X-0 标注的 122 条重放：
**决策与人工标注 100% 一致（0 误杀 / 0 漏放）**。

---

## 5. 数据库变更与播种

```
alembic_version = p27_keyword_rule_config   ✅ 迁移已应用
keywords(id=30, word=大厂).rule_config = {...11 个键, anchor=大厂}  ✅ 已播种
其余 keywords.rule_config = NULL (count=0)  ✅
```

- 迁移前已运行 `scripts/db_identity_check.py` 门禁 → **VERIFIED**（生产库，非测试库）。
- 运行时链路：`service._build_dachang_filter(db)` 优先读 `get_keyword_rules(db)` 中 `大厂` 规则，
  列缺失/未播种/异常 → 回退内置 `DEFAULT_RULE`（满足「保留代码默认 fallback，避免迁移时序问题」）。

---

## 6. 作用点说明（防御纵深）

| 作用点 | 位置 | 作用 |
|---|---|---|
| ① 采集入口收口 | `CollectorService._process_collector` 主循环 | 互联网「大厂」噪声**在入库前直接丢弃**（主防线） |
| ③ 区域标签防御 | `OpinionRegionService._region_hits` | 裸别名 `"大厂"→131028` 经语义过滤；即便绕过①也不会被误贴大厂回族自治县标签 |

其余关键词（地域/主题）在两个作用点均不介入，行为完全不变。

---

## 7. 未做 / 待办

- ❌ 不清理历史 73 条噪声 → 另立 **Phase X-History**（审计清单见 `_audit_dachang_backtest.json`）。
- ❌ 不增加 UI 规则编辑入口（本阶段仅后端治理）。
- ❌ 不改动其他关键词匹配逻辑、不引入 AI/新依赖、不全局替换「大厂」。
- ⏭ 上线后建议观察 `dachang_filtered` 计数器，确认拦截量符合预期。
