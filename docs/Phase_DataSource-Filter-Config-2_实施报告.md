# Phase DataSource-Filter-Config-2 实施报告

> 阶段目标：将「专用型数据源过滤策略」从代码硬编码升级为完全由 `data_sources.config_json` 控制，
> 同时保持当前廊坊区域舆情监测能力与生产采集量完全不变。
> 本阶段仅改「配置读取逻辑」与「配置校验逻辑」，未触碰 Opinion/Event/Risk 模型、scheduler、registry、
> collector 数据获取机制（HTTP 抓取不变）、dashboard、前端、migration、数据库表结构/数据。

---

## 1. 审计发现（只读）

| 采集器 | 是否读取 `filter_mode`/`keyword_scope` | 默认行为 | 结论 |
|--------|----------------------------------------|----------|------|
| 新华网 | ✅ | `region_or_topic` | 已配置化 |
| 人民网 | ✅ | `region_or_topic` | 已配置化 |
| 中国新闻网 | ✅ | `region_or_topic` | 已配置化 |
| **百度新闻** | ❌ 硬编码 `region_kw` 驱动搜索 | `region_only` | **未配置化 → 本阶段改造点** |
| 大厂县政府网站 | 故意全量（Option B），不参与过滤 | 全量 | 超出 4 个目标源范围，不改 |

配置校验缺口：`validate_data_source_config` 仅校验 `national` 模式，regional 模式下
`filter_mode`/`keyword_scope` 交叉一致性缺失（如 `region_only`+`topic`、`topic_only`+`region` 可写入）。

管理接口：`admin_data_sources.py` 的 `DEDICATED_ALLOWED_KEYS` 已含 `filter_mode`/`keyword_scope`，
`POST`/`PATCH` 均经 `_validate_collection_config`；`source_type`/`class_path`/`key` 不在 PATCH 可变字段
→ 「不允许修改 source_type / 系统约束」已天然满足，**无需改 allowlist**。

---

## 2. 修改文件

| 文件 | 类型 | 变更 |
|------|------|------|
| `app/collectors/baidu_news_collector.py` | 修改 | ① 新增 `DEFAULT_FILTER_MODE="region_only"` / `DEFAULT_KEYWORD_SCOPE="region"` 常量；② 导入 `apply_keyword_scope`；③ `fetch` 读取 `cfg.filter_mode()` / `cfg.keyword_scope()`，按 `filter_mode` 选择搜索关键词集（`region_only`→地域词、`region_or_topic`→地域+主题、`topic_only`→主题词），空关键词集触发 fail-safe 返回 `[]`。 |
| `app/collectors/source_config.py` | 修改 | `validate_data_source_config` 在 regional/缺省分支补充 `filter_mode`/`keyword_scope` 取值校验与交叉一致性校验（`region_only`+`topic` 拒绝、`topic_only`+`region` 拒绝），并把 `national` 分支提前 `return` 以避免复用 regional 校验。 |
| `docs/Phase_DataSource-Filter-Config-2_PreAudit.md` | 新增 | 只读预审计文档 |
| `backend/_verify_datasource_filter_config.py` | 新增 | 只读 + 沙盒验证脚本（26 项全 PASS） |
| `docs/Phase_DataSource-Filter-Config-2_实施报告.md` | 新增 | 本文件 |

**未触碰**：Opinion/Event/Risk 模型、`region_id` nullable、scheduler、registry、collector 数据获取机制
（仍向百度新闻按关键词检索，仅「选词」由配置决定）、common.py、`matches_region_topic`（topic_only 在
Config-1 已就绪）、dashboard、前端、任何 migration、任何数据库表结构/数据行。

---

## 3. 修改后链路

统一来源：`DataSource.config_json`

```
{
  "filter_mode": "region_or_topic" | "region_only" | "topic_only",
  "keyword_scope": "region_topic" | "region" | "topic"
}
```

各源解析（缺省回退各自历史默认）：

| 数据源 | 空 `config_json` 解析 | 与改造前一致 |
|--------|----------------------|--------------|
| 百度新闻 | `region_only` + `region` | ✅（改造前即仅地域词搜索） |
| 新华网 | `region_or_topic` | ✅ |
| 人民网 | `region_or_topic` | ✅ |
| 中国新闻网 | `region_or_topic` | ✅ |

百度新闻 `fetch` 新逻辑：

```
cfg = self.source_config
filter_mode = cfg.filter_mode("region_only")          # 配置优先，默认 region_only
region_kw, topic_kw = apply_keyword_scope(cfg.keyword_scope(), region_kw, topic_kw)
if filter_mode == "topic_only":     selected = topic_kw
elif filter_mode == "region_or_topic": selected = region_kw + topic_kw
else:                               selected = region_kw      # 默认
# 去重 → 空则 fail-safe 返回 []
for kw in selected: 检索百度新闻 ...                       # 数据获取机制不变
```

---

## 4. 默认行为不变（Goal 3 验证）

- 全部 5 个专用型源 `config_json` 在数据库中仍为 `'{}'` → 本阶段**未改任何源配置**。
- 百度新闻空配置 → `region_only` → 仍以地域词向百度检索（与改造前逐字一致）。
- 新华/人民/中国新闻网空配置 → `region_or_topic`（与各自 `DEFAULT_FILTER_MODE` 一致）。
- 因默认未变，**生产采集量零变化**（验证期 opinions 仍由线上调度器正常产生，非本阶段所致）。

---

## 5. 配置校验规则（Goal 4）

`validate_data_source_config(config)` 返回规范化 `config`，非法组合抛 `ValueError`（明确 422，不静默修正）：

| 配置 | 结果 |
|------|------|
| `{}` / 仅 `filter_mode`/`keyword_scope` 单边 | 合法（单边不交叉校验，读取侧应用默认） |
| `{filter_mode:region_only, keyword_scope:region}` | 合法 |
| `{filter_mode:topic_only, keyword_scope:topic}` | 合法 |
| `{filter_mode:region_or_topic, keyword_scope:*}` | 合法（并集，任意范围） |
| `{filter_mode:region_only, keyword_scope:topic}` | **拒绝** |
| `{filter_mode:topic_only, keyword_scope:region}` | **拒绝** |
| `filter_mode`/`keyword_scope` 取值不在允许集 | **拒绝** |
| `collection_mode:national` + 非 `topic_only`/`topic` | **拒绝**（National-3 既有规则保留） |

---

## 6. 管理接口支持（Goal 5）

- 通用型：`GENERIC_ALLOWED_KEYS` 已含 `filter_mode`/`keyword_scope`/`collection_mode`；`POST`/`PATCH`
  经 `_validate_generic_config` + `_validate_collection_config` 校验 → 支持且受组合约束。
- 专用型：`DEDICATED_ALLOWED_KEYS = STRATEGY_KEYS | {collection_mode}` 已含 `filter_mode`/`keyword_scope`；
  `POST`/`PATCH` 经 `_validate_collection_config` 校验 → 支持且受组合约束（验证 D 组确认专用型
  `topic_only` 可保存、非法组合拒绝）。
- `source_type` / `class_path` / `key` **不在 PATCH 可变字段** → 不允许修改 source_type / 系统约束已天然满足。

---

## 7. 验证结果

运行 `backend/.venv/Scripts/python.exe _verify_datasource_filter_config.py`（只读 + 沙盒），**26/26 PASS**：

```
[A] 旧配置 {} 解析：百度=region_only / 新华=region_or_topic / 人民=region_or_topic / 中国新闻=region_or_topic / 通过 validate
[B] 百度空配置 region_only + keyword_scope=region + is_national=False
[C] 新华空配置 region_or_topic + is_national=False
[D] 专用型(百度) topic_only 经 _validate_create 接受 / region_only 接受 / 通用型 topic_only 接受 / _validate_collection_config 接受
[E] region_only+topic 拒绝 / topic_only+region 拒绝 / 专用型拒绝(admin) / 通用型拒绝(admin)
[F] regions=24 / 哨兵存在 / 无 opinion·event 指向哨兵 / events=175 / alerts=11 /
    5 个专用型源 config_json 仍为 '{}'（未改任何源配置 → 未扩大采集范围）/ opinions>=1027
```

补充无网络冒烟测试确认：百度 `fetch` 按 `filter_mode` 选择关键词集（topic_only 仅搜主题词、
region_or_topic 搜地域+主题）、空关键词集触发 fail-safe 返回 `[]`，代码路径运行无异常。

---

## 8. 生产影响评估

| 维度 | 结论 |
|------|------|
| 数据库结构 | 无变化（无 migration / 新字段 / 新表） |
| 数据库数据 | 无写入（regions/opinions/events/alerts 均无本阶段 INSERT/UPDATE；5 个专用型源配置未改） |
| 现有 38 个数据源 | 均未声明非默认 `filter_mode`，读取侧回退历史默认 → 生产采集行为零变化 |
| 百度新闻 | 默认 `region_only` 与改造前一致；仅当选管理员显式配置 `topic_only`/`region_or_topic` 时才改变选词 |
| scheduler / registry / collector 抓取机制 | 未改动 |
| Event / Risk 链路 | 不受影响 |
| ⚠️ 部署提示 | 运行中的 uvicorn 仍加载本阶段之前代码；新逻辑需重启后端方在生产生效（按「不擅自 kill uvicorn」约定，本阶段未重启；验证靠全新模块导入 + 冒烟完成；上线重启为独立运维动作） |

---

## 9. 回滚方式

完全可回滚，不涉及数据库数据：

- `baidu_news_collector.py`：删除 `DEFAULT_FILTER_MODE`/`DEFAULT_KEYWORD_SCOPE` 常量、`apply_keyword_scope`
  导入，将 `fetch` 关键词选择块恢复为原 `if region_kw is not None: kws = region_kw ...` 分支。
- `source_config.py`：将 `validate_data_source_config` 中 regional 交叉一致性校验块删除，并把 `national`
  分支的 `return config` 改回原 `return config` 统一出口（与 National-3 原状一致）。

回滚后系统回到 National-4 完成态（专用型过滤仍由代码默认驱动，配置校验仅含 national 规则）。

---

## 10. 验收标准核对

| 验收项 | 状态 |
|--------|------|
| 专用型过滤策略完全由 `config_json` 控制 | ✅（百度补齐读取；xinhua/people/chinanews 已具备） |
| 百度新闻空配置 → region_only（默认不变） | ✅ |
| 新华/人民/中国新闻网空配置 → region_or_topic（默认不变） | ✅ |
| 显式 `filter_mode=topic_only` 可保存（通用型 + 专用型） | ✅ |
| 非法组合（region_only+topic / topic_only+region）拒绝 | ✅ |
| 数据库 regions/opinions/events/alerts 数量不变化 | ✅ |
| 未扩大采集范围（5 个专用型源配置未改） | ✅ |
| 未修改 Opinion/Event/Risk / scheduler / registry / collector 抓取机制 | ✅ |
| 未新增字段/表/migration | ✅ |
| 不改变当前廊坊区域监测能力 | ✅ |

结论：Phase DataSource-Filter-Config-2 完成，所有验收项通过。
系统从「专用型过滤规则隐藏在代码里」升级为「所有数据源过滤策略由 config_json 控制」，同时当前区域监测能力完全不变。
