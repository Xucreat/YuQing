# Phase DataSource-Filter-Config-3 实施报告

## 阶段目标

将 `DataSource.config_json` 中已有的 `filter_mode` / `keyword_scope` 能力暴露到管理员前端，
实现数据源过滤策略的**可视化配置**。仅做管理能力，不改变采集行为。

本阶段是纯前端暴露任务：后端（Phase DataSource-Filter-Config-2）已完成配置化与校验，
现有 `POST /admin/data-sources` 与 `PATCH /admin/data-sources/{id}` 接口已支持
`filter_mode` / `keyword_scope`（经 `DEDICATED_ALLOWED_KEYS` / `GENERIC_ALLOWED_KEYS` 与
`validate_data_source_config` 区域交叉一致性校验）。本阶段把这两个字段从「仅 raw JSON 文本」
升级为「下拉可视化配置」。

---

## 一、前端审计（只读）

检查对象：`frontend/src/views/Sources.vue`（数据源管理页面，含列表 / 配置弹窗 / 新建弹窗）。

**审计结论：**

| 位置 | 改造前 `config_json` 展示方式 | 结论 |
|------|------------------------------|------|
| 配置弹窗（编辑现有源，行「配置」按钮） | 通用型：raw JSON `el-input textarea`；专用型：**隐藏 textarea + 只读提示「无需填写」**，且「保存配置」按钮对专用型隐藏 | 过滤策略不可视化 |
| 新建采集源弹窗 | raw JSON `el-input textarea`（含默认模板 `DEFAULT_CONFIG`） | 过滤策略不可视化 |
| 列表页 | 展示 `keyword_mode` / `effective_keywords`（另一套关键词策略字段，**非本阶段对象**） | 不涉及 |

**关键约束确认：**
- 专用型源此前在配置弹窗中**完全无法保存** `config_json`（按钮被 `v-if` 隐藏）。本阶段必须放开，
  否则管理员无法为百度新闻等专用型源设置 `filter_mode`（这正是 Phase 2 配置化的落点）。
- 后端对专用型的保存契约：仅允许空配置 `{}` 或「仅含策略键 / collection_mode」。因此前端对专用型
  **隐藏 raw textarea**，只暴露 `filter_mode` / `keyword_scope` 下拉；保存时以原有 `config_json`
  为基础**合并**下拉值（保留 `collection_mode` 等既有键，杜绝误删）。
- 通用型保留 raw textarea（供 `list_urls` / `keywords` 等高级键编辑），下拉与 textarea 共享
  `config_json`，保存时下拉值覆盖对应键。

---

## 二、修改文件

### 唯一修改的前端文件：`frontend/src/views/Sources.vue`

| 区块 | 变更 |
|------|------|
| `<script>` 选项与规则 | 新增 `filterModeOptions` / `keywordScopeOptions`（含中文显示文案）、`scopeDisabledFor()`（联动禁用）、`illegalComboError()`（非法提示，与后端 `validate_data_source_config` 文案一致） |
| 配置弹窗模板 | 新增「过滤策略」分区：`filter_mode` / `keyword_scope` 两个 `el-select`；**专用型不再隐藏「保存配置」按钮**，专用型仅显示下拉（隐藏 raw textarea），通用型显示「下拉 + 高级 config_json textarea」；非法组合实时红字提示 |
| 新建弹窗模板 | `config_json` 文本域下方新增「过滤策略（可选）」分区：`filter_mode` / `keyword_scope` 两个 `el-select` + 实时非法提示 |
| 状态 | `form` 增加 `filter_mode` / `keyword_scope`；新增 `filterModeDraft` / `keywordScopeDraft`（配置弹窗草稿） |
| `openConfig()` | 解析现有 `config_json` 填入下拉（`{}` → 显示「默认（不指定）」）；专用型保留原 `config_json` 以便保存时合并 |
| `saveConfig()` | 校验非法组合 → 合并下拉值到 `config_json`（专用型以原值为底保留 `collection_mode`，通用型以 textarea 为底）→ `PATCH`；下拉留空则删除对应键（不覆盖采集器默认） |
| `buildPayload()`（新建） | 合并下拉值到 `config_json`；留空则删除对应键 |
| `testCreate()` / `submitCreate()` | 保存前调用 `illegalComboError` 前端拦截非法组合 |
| `onConfigFilterModeChange()` / `onCreateFilterModeChange()` | 切换 `filter_mode` 后若当前 `keyword_scope` 变为非法，自动清空 `keyword_scope` |
| 样式 | 新增 `.cf-divider` / `.filter-row` / `.cf-half` |
| 表单重置 | `submitCreate` 成功后重置 `filter_mode` / `keyword_scope` |

### 后端文件

**未修改任何后端文件。** Phase 2 已具备：
- `app/api/admin_data_sources.py`：`DEDICATED_ALLOWED_KEYS` / `GENERIC_ALLOWED_KEYS` 含
  `filter_mode` / `keyword_scope`；`POST`/`PATCH` 均经 `_validate_collection_config` →
  `validate_data_source_config`（区域交叉一致性校验，拒绝 `region_only+topic` / `topic_only+region`）。
- `app/collectors/source_config.py`：`validate_data_source_config` 区域分支交叉校验。

### 新增验证脚本（测试用，非生产）

- `backend/_verify_frontend_filter_config.py`：TestClient 集成测试（测试库 `:5433/opinion_test`，
  用完清理）+ 生产库只读校验（`:5432/opinion_db`）。

---

## 三、UI 行为（修改后链路）

统一来源仍是 `DataSource.config_json`：
```json
{
  "filter_mode": "region_only | region_or_topic | topic_only",
  "keyword_scope": "region | region_topic | topic"
}
```

- **旧数据 `config_json={}`**：下拉回退为「默认（不指定）」→ 页面正常显示默认策略，保存后仍为 `{}`
  （下拉留空即删除对应键，不写入默认值），采集行为零变化。
- **专用型（百度/新华/人民/中国新闻）**：弹窗显示两个下拉（不再隐藏），管理员可显式指定
  `filter_mode` / `keyword_scope`；其余配置保持 `{}`。
- **通用型**：下拉 + 高级 `config_json` textarea 并存，下拉对两个策略键有最终决定权。

下拉选项与显示：

| 字段 | value | 显示 |
|------|-------|------|
| `filter_mode` | `''`（默认） | 默认（不指定，按采集器默认） |
| | `region_only` | 仅地域 |
| | `region_or_topic` | 地域或主题 |
| | `topic_only` | 仅主题 |
| `keyword_scope` | `''`（默认） | 默认（不指定，按采集器默认） |
| | `region` | 地域词 |
| | `region_topic` | 地域+主题词 |
| | `topic` | 主题词 |

---

## 四、联动规则（前端禁止非法组合）

与后端 `validate_data_source_config` 保持一致：

| 组合 | 前端行为 | 后端行为 |
|------|----------|----------|
| `region_only` + `topic` | `keyword_scope=topic` 选项**禁用**；若由切换触发则自动清空；实时红字提示 | `PATCH`/`POST` 返回 **422** 拒绝 |
| `topic_only` + `region` | `keyword_scope=region` 选项**禁用**；自动清空；实时红字提示 | `PATCH`/`POST` 返回 **422** 拒绝 |
| `region_or_topic` + `region_topic` | 允许 | 允许 |
| `region_or_topic` + 任意 `keyword_scope` | 允许（并集） | 允许 |

实现：`<el-option :disabled="scopeDisabledFor(filterModeDraft, o.value)">` + `illegalComboError()`
实时提示 + 保存前 `illegalComboError` 拦截。后端为最终权威闸门（422）。

---

## 五、保存接口（复用，未新增）

| 操作 | 接口 | 说明 |
|------|------|------|
| 编辑现有源过滤策略 | `PATCH /api/admin/data-sources/{id}`（body `{config_json}`） | 复用既有接口；专用型按钮已放开 |
| 新建源时指定过滤策略 | `POST /api/admin/data-sources`（body 含 `config_json`） | 复用既有接口；`buildPayload` 合并下拉 |

**未新增任何接口。** `/api` 前缀为前端代理约定（前端调用即 `/api/admin/data-sources`）。

---

## 六、验证结果

### 6.1 前端构建（frontend build）
```
node --max-old-space-size=1400 node_modules/vite/bin/vite.js build
✓ built in 18.56s   （退出码 0）
```
构建产物 `dist/assets/index-*.js` 含新文案「地域或主题 / 仅地域 / filter_mode」，确认组件已编译进包。

### 6.2 后端 API 测试（`_verify_frontend_filter_config.py`，12/12 PASS）
测试库 `:5433/opinion_test`（已迁移 schema），临时源用完 `DELETE` 清理；生产库仅只读。

```
[PASS] A  专用型有效 filter_mode 保存(PATCH 200)
[PASS] A1 保存内容含 filter_mode=topic_only
[PASS] B  专用型非法组合拒绝(PATCH 422)
[PASS] C  通用型有效过滤策略保存(PATCH 200)
[PASS] C1 保存内容含 filter_mode/keyword_scope
[PASS] D  通用型非法组合拒绝(PATCH 422)
[PASS] E  专用型 POST 非法组合拒绝对外(_validate_create)
[PASS] F  专用型 POST 有效 filter_mode 通过校验
[PASS] G  通用型 POST 非法组合拒绝对外(_validate_create)
[PASS] H  空配置 {} 对专用型合法(默认策略)
[PASS] I  生产数据源总数=38（未变化）
[PASS] I1 专用型源 config_json 未变化(均为{})
```

422 详情示例：
`filter_mode=region_only 与 keyword_scope=topic 矛盾（仅地域过滤不应使用纯主题词范围），已拒绝`

### 6.3 验收点逐条核对
1. **旧数据 `config_json={}` 页面正常显示默认策略** —— 前端下拉回退「默认（不指定）」；后端测试 H 通过。
2. **修改策略可以保存** —— 测试 A / C 通过（专用型 + 通用型 PATCH 200，内容含策略键）。
3. **非法组合前后端均拒绝** —— 前端禁用选项 + 红字提示；后端测试 B / D / E / G 返回 422。
4. **数据库无新增字段** —— 本阶段零后端改动、零 migration；验证脚本仅测试库读写 + 生产只读。
5. **已有 38 个数据源配置不变化** —— 生产只读校验 I / I1：总数=38、5 个专用型源 `config_json` 仍为 `{}`。

---

## 七、生产影响评估

| 维度 | 结论 |
|------|------|
| 数据库结构 | 无变化（无 migration / 新字段 / 新表） |
| 数据库数据 | 无写入生产；验证脚本仅测试库临时源（已清理）+ 生产只读 SELECT |
| 38 个数据源 | 均未声明非默认 `filter_mode`，且前端下拉默认「不指定」→ 不写键 → 采集量零变化 |
| 专用型源（百度等） | 此前无法在前端设 `filter_mode`；现可设，但默认仍「不指定」= 沿用采集器默认（与改造前一致） |
| collector 抓取逻辑 / scheduler / registry | 未改动 |
| Opinion / Event / Risk 模型 | 未改动 |
| Event / Risk 链路 | 不受影响 |
| ⚠️ 部署提示 | 前端构建产物 `dist/` 需随下次发布/静态托管刷新生效；运行中的 uvicorn 仍加载既有后端代码
（本阶段未改后端，无需重启后端）。按「不擅自 kill uvicorn」约定，本阶段未重启。 |

---

## 八、回滚方式

完全可回滚，不涉及数据库数据：
- `frontend/src/views/Sources.vue`：删除「过滤策略」分区模板、相关 `<script>` 选项/函数/
  状态/逻辑（`filterModeOptions` / `keywordScopeOptions` / `scopeDisabledFor` /
  `illegalComboError` / `filterModeDraft` / `keywordScopeDraft` / `onConfigFilterModeChange` /
  `onCreateFilterModeChange` 及 `saveConfig`/`buildPayload`/`openConfig` 中的合并逻辑），
  恢复专用型「保存配置」按钮的 `v-if` 隐藏，恢复原 raw textarea 直存逻辑。
- 重新 `vite build` 发布。
- 回滚后系统回到 Phase 2 完成态（过滤策略仅可由 raw JSON 配置，前端无可视化下拉）。

---

## 九、明确未做（遵守红线）

- 未修改 Opinion / Event / Risk 模型
- 未修改 collector 抓取逻辑
- 未修改 scheduler / registry
- 未新增数据库字段
- 未新增 migration
- 未批量修改已有 `data_sources.config_json`（验证 I1 证实 5 个专用型源仍为 `{}`）
- 未进入 National-Mode（前端全国展示 / 灰度切换）

---

## 十、交付文件

1. `docs/Phase_DataSource-Filter-Config-3_实施报告.md`（本文件）
2. `backend/_verify_frontend_filter_config.py`（后端 API 验证脚本，12/12 PASS，测试库可重复运行）
3. `frontend/src/views/Sources.vue`（修改源码，含过滤策略可视化 UI）
4. `frontend/dist/`（构建产物，随发布刷新生效）

**结论：** Phase DataSource-Filter-Config-3 完成。数据源过滤策略 `filter_mode` / `keyword_scope`
已从「仅 raw JSON」升级为「管理员前端下拉可视化配置」，联动规则与后端校验一致，非法组合前后端均拒绝，
生产 38 个数据源配置零变化，采集行为完全不变。
