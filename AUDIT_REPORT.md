# YQ 交付前全面审计报告（复测版）

## 1. 执行摘要

本报告记录 2026-08-10（Asia/Shanghai）对当前工作区 YQ 系统的第二轮交付前只读审计。上一轮发现的修复已通过 Codex in-app Browser 实际复测；本轮继续覆盖认证、路由、查询页面、外网工作区、事件/告警详情、响应式布局和构建健康检查。

结论：**GO WITH RISKS**。后端静态发布入口 `http://127.0.0.1:8000` 可用，未发现 Blocker、Critical、High 或 Medium 级活动缺陷；当前活动问题为 Low 级 1 项（AUDIT-009），历史 AUDIT-001~008 已修复并复验。`git diff --check` 因既有用户修改文件的尾随空白失败，且外网事件型告警、真实外部失败注入和多角色越权仍未在隔离环境端到端覆盖。原 AUDIT-008（外网告警标题不可点击）已修复并复验：文章型标题打开舆情详情，按钮支持 Enter/Space，聚焦时出现可见焦点环。由于当前 `foreign_events=0`，事件型标题只完成代码路径和空状态验证，未用真实事件告警记录端到端验证。

本轮及上一轮已复验修复：移动 Dashboard 溢出、Opinions 筛选/分页 URL 状态、Events 窄屏详情入口、角色标签重复、外网详情正文重复、文档硬编码密码、Vite 启动目录问题。自动采集、AI、Dry-Run、事件确认、告警处置写操作、调度和外部通知均未执行。

## 2. 审计范围与边界

覆盖：登录/登出/错误认证/受保护路由、Dashboard、Opinions、Events、Alerts、Foreign Workspace（Dashboard/舆情/事件/告警/规则）、Data、AI Search、Propagation、Command Screen、用户/角色/登录日志/操作日志，以及桌面、平板和移动视口。

路由清单：`/login`、`/dashboard`、`/opinions`、`/foreign`、`/ai-search`、`/ai-search/web`、`/ai-search/ai`、`/ai-search/anspire`、`/opinion/:id`、`/events`、`/event/:id`、`/alerts`、`/propagation`、`/command-screen`、`/data`、`/system/users`、`/system/roles`、`/system/login-logs`、`/system/operation-logs`，以及兼容重定向入口。

严格只读：未修改源代码、配置、数据库或部署环境；未创建/确认候选或正式事件；未执行 RSS、AI、代理、自动任务、告警评估、外部通知或破坏性 CRUD。仅更新本报告和 `audit-evidence/`。

## 3. 测试环境与启动方式

| 项目 | 结果 |
|---|---|
| 后端 | 既有 `uvicorn app.main:app --host 0.0.0.0 --port 8000` 实例 |
| 实际地址 | `http://127.0.0.1:8000` |
| 健康检查 | HTTP 200；`status=ok`；`collector_discovery=db_driven` |
| 浏览器 | Codex in-app Browser，实际交互；1440x900、768x1024、390x844 |
| 复测时间 | 2026-08-10（+08:00；浏览器补测与命令检查在本日完成） |
| Vite 5173 | 当前无监听（连接被拒绝）；本轮使用 8000 后端静态构建。该项是环境限制，不是 8000 发布入口故障。 |

## 4. 功能清单与覆盖矩阵

| 模块 | 正常路径 | 空/错误/边界 | 刷新/深链/响应式 | 结果 |
|---|---|---|---|---|
| 认证与权限 | 登录、退出 | 错误密码、空字段、未登录受保护路由 | 退出后后退、刷新 | PASS |
| Dashboard | 指标、趋势、导出弹窗 | 空报告名观察 | 390/768/1440 视口；无溢出 | PASS（修复复验） |
| Opinions | 搜索、来源、分页 | 无结果、清空 | URL 查询和刷新保持 | PASS（修复复验） |
| Events | 列表、筛选、真实详情 | 空状态 | 窄屏表格 + 可见“查看”按钮 | PASS（修复复验） |
| Alerts | 规则/记录/处置历史只读查看 | 状态/严重度筛选 | tabs 切换 | PASS；标题点击见 AUDIT-008 |
| Foreign Workspace | Dashboard、舆情、事件、告警、规则 | 0 候选/0 正式事件 | 768/390 视口、详情弹窗 | PASS；事件告警路径未覆盖 |
| Data | 关键词、来源、采集日志、AI 线索 | 空筛选 | tabs/深链 | PASS（只读） |
| AI Search | 页面、子路由、空关键词校验 | 空检索 | 深层路由 | PASS；未调用外部服务 |
| Propagation/Command | 图谱、时间线、LIVE/KPI | 初始加载态 | 深链/视口 | PASS |
| System admin | 用户、角色、登录/操作日志 | 只读权限检查 | 深层路由 | PASS（标签修复复验） |

## 5. 已执行的浏览器流程

1. 错误密码收到 401/安全错误摘要，空字段显示必填提示；使用本地已配置凭据完成登录和退出。
2. 直接访问受保护路由，未登录被送回 `/login`；本轮用 Browser `goBack()`/`goForward()` 验证 `/dashboard` 与 `/foreign?tab=alerts` 历史导航，登出后后退及直接访问 `/dashboard` 均未恢复受保护数据。
3. Opinions 使用不存在关键词得到空状态；使用 `新华网` 搜索并切换第 2 页；复测 URL 为 `/opinions?source=新华网&page=2`，刷新后状态保持。
4. Dashboard 打开导出弹窗并取消；未生成文件或写入业务数据。移动复测 `clientWidth=375`、`scrollWidth=375`、`body.scrollWidth=375`，无溢出元素。
5. Events 在 768x1024 下保留宽表横向滚动，但每行可见“查看”按钮；点击进入真实 `/event/634` 详情。
6. Foreign 复测 Dashboard、舆情、事件、告警、规则；自动聚合/自动告警/调度/外部通知均显示关闭；详情正文仅渲染一次。
7. Foreign 告警只读打开“处置历史”，确认/解决历史包含状态迁移、备注、操作人和时间；未点击处置、确认、解决、抑制或 Dry-Run。
8. 点击外网告警标题文字本身打开文章详情；使用 Enter/Space 触发同一动作。标题现为语义化按钮，聚焦时有可见蓝色焦点环；事件型标题因无真实事件行未端到端覆盖。
9. Data、AI Search、Propagation、Command Screen、System admin 完成只读导航和空态/加载态检查；未调用外部 AI、采集或通知。

## 6. 缺陷列表（严重级别）

### Low

#### AUDIT-009：`git diff --check` 被既有修改文件的尾随空白阻断

- 模块：交付前质量门禁。
- 前置条件：工作区保留用户已有修改；本次审计不允许清理源文件。
- 复现：在仓库根目录执行 `git diff --check`。
- 实际结果：当前未暂存差异命令失败，报告 `ForeignKeywordsView.vue:52-54` 的尾随空白；复核输出和退出码见 `audit-evidence/AUDIT-command-checks-20260810-rerun.txt`。较早快照 `AUDIT-command-checks-20260810.txt` 记录过三个文件，反映的是审计前另一工作区暂存状态。
- 预期结果：质量门禁无输出并返回 0。
- 影响：可能阻断 CI/发布流水线；不影响当前运行中的 8000 静态入口。
- 稳定性：稳定复现，来源是审计前已有工作区修改。
- 建议：在独立提交中由代码所有者清理尾随空白后重新运行门禁；本审计未改动这些文件。

### Medium（已修复）

#### AUDIT-008：外网告警标题本身不可点击 —— 已修复（2026-08-10）

- 模块：`/foreign?tab=alerts` 外网告警列表。
- 根因：标题渲染为纯 `<strong class="alert-title">`，无点击/键盘语义；而“关联文章”按钮复用的 `openOpinion` 详情打开逻辑未绑定到标题。
- 修复：`ForeignWorkspace.vue` 标题改为可点击 `<button class="alert-title alert-title-link">`，新增 `openAlertTarget(row)`——`foreign_opinion_id` 存在时复用 `openOpinion` 打开舆情详情弹窗，`foreign_event_id` 存在时切换到 events 标签页并调用既有 `loadEventDetail` 渲染内联详情；补 `role`/`tabindex`/`@keydown.enter|space`/`focus-visible` 键盘与焦点语义。CSS 仅重置按钮外观并加 hover 蓝色下划线，不破坏现有观感。
- 复验：`vite build` 通过，部署产物含 `openAlertTarget` 及点击/Enter/Space 处理器；`/health` 200；文章型真实告警标题点击和键盘触发均成功。`git diff --check` 的当前失败与该修复无关，见 AUDIT-009。
- 影响：外网告警体验修复；不影响国内链路、数据完整性或后端。
- 剩余限制：事件型标题路径因 `foreign_events=0` 未用真实记录端到端验证，仅代码级复用既有机制。

### 已修复并复验（不再计入当前缺陷）

| 原编号 | 修复与复验证据 |
|---|---|
| AUDIT-001 | Opinions 查询、来源和分页写入 URL，刷新保持；`RETEST` 流程已验证。 |
| AUDIT-002 | 移动 Dashboard 无横向溢出；`RETEST-mobile-dashboard-fixed.png`。 |
| AUDIT-003 | Events 新增可见“查看”按钮并进入 `/event/634`；`RETEST-events-view-button.png`。 |
| AUDIT-004 | 文档移除硬编码管理员密码，改为 `INIT_ADMIN_PASSWORD` 注入说明。 |
| AUDIT-005 | Foreign detail summary/content 相同只显示一段；`RETEST-foreign-detail-fixed.png`。 |
| AUDIT-006 | Roles 页面不再重复显示相同 code/name；`RETEST-role-labels-fixed.png`。 |
| AUDIT-007 | Vite 启动目录修复已在上一轮验证；本轮 5173 未启动，作为环境限制记录。 |
| AUDIT-008 | 外网告警标题改为可点击按钮，按文章/事件类型打开对应详情；`RETEST-alert-title-not-clickable.txt` 对应现象已消除。 |

## 7. 外网及第三方依赖专项

- 最新浏览器快照显示外网文章 29 条、5 个有数据来源、风险完成 29、候选 0、正式事件 0、告警 1 条；读数可能随只读刷新时间变化。
- 外网事件页：自动聚合已停用、调度已注册否；外网告警页：自动告警评估已停用、调度已注册否、外部通知已停用。
- 只读检查了 7 个来源、语言统计、采集日志和外网详情；未执行真实 RSS、来源测试、代理、AI、翻译或网络通知。
- 当前没有外网正式事件或外网事件告警行，因此“事件告警标题 → 外网事件详情弹窗”无法用真实数据验证；这是数据覆盖限制，不伪造候选或事件。
- 浏览器工具本轮未提供可靠 DNS/连接失败、4xx/5xx、超时、响应格式篡改或离线拦截注入，因此真实外网降级和恢复重试仍是剩余风险。一次 Statsig 遥测超时属于 Browser 工具噪声，未计为本地应用错误。

## 8. 权限、安全与国内链路隔离

- 未登录访问受保护路由被重定向 `/login`；登出后后退未恢复业务内容。
- 仅使用现有 admin 会话进行非破坏性检查；未创建第二账号、未做跨用户 ID 篡改、删除、停用或越权写入。
- 页面未显示密码、JWT、代理密钥或令牌；外网原文链接使用 `rel="noopener"`。未发现文件上传、支付、OAuth 或 Webhook 页面入口。
- 未执行 opinions、events、alerts、Dashboard、地图、热词、scheduler 或国内事件链路写操作。外网页面明确声明只读 foreign_* 链路，自动任务和外部通知关闭。
- 认证失败产生预期登录审计记录；没有新增候选、正式事件或正式事件审计记录。

## 9. 响应式与可访问性

已浏览 1440x900、768x1024、390x844。Dashboard 移动溢出已消除；Events 表格和 Foreign alerts 表格使用内部水平滚动，不造成页面级溢出；Foreign、Command Screen 和对话框未见遮挡。登录用户名输入框聚焦时出现可见 `box-shadow` 焦点环，外网告警标题支持 Enter/Space。未完成全量 WCAG 对比度、屏幕阅读器、完整 Tab 顺序和触摸手势审计。

## 10. 测试结果

- 浏览器主流程与修复复测：PASS，证据见 `audit-evidence/`。
- 本地页面控制台：未发现应用级关键错误；唯一观测到的 Statsig POST 超时属于 Browser 工具遥测噪声，未计入产品缺陷。
- 后端 `GET /health`：PASS，HTTP 200，`status=ok`。
- `python -m compileall -q backend/app`：PASS。
- `frontend npm run build`：PASS（Vite 5.4.21；仅第三方 PURE 注释和分包提示）。
- `git diff --check`：FAIL；当前未暂存的 `ForeignKeywordsView.vue:52-54` 存在尾随空白，详见 AUDIT-009 和 `audit-evidence/AUDIT-command-checks-20260810-rerun.txt`。本次审计未清理源文件。
- 数据库和生产快照：本轮保持只读；未运行采集、Dry-Run、AI、事件/告警写操作。

## 11. 未覆盖项目及原因

- 新增/编辑/删除关键词、来源、规则、用户、角色，事件确认/合并/拆分，告警确认/解决/抑制：只读边界禁止写入。
- 真实 RSS、DNS/TLS、代理认证、超时、4xx/5xx、外部 AI、翻译和通知：用户明确禁止且工具未提供可靠故障注入。
- 外网事件告警详情：当前 `foreign_events=0`，没有真实可点击样本。
- 文件上传/下载/预览、OAuth、支付、邮件、Webhook：路由和导航未发现可用入口。
- 多角色真实登录和越权修改：未创建或使用额外测试账号。
- 全量键盘、屏幕阅读器、精确色彩对比度和触摸手势：本轮未完成。

## 12. 剩余风险

外网真实失败降级、跨语言候选质量、AI/代理供应商可用性、自动任务重启后的状态和事件告警详情仍需要隔离环境验证。当前外网数据量小且正式事件为 0，不能据此证明生产覆盖率。5173 未运行意味着开发入口无法在本轮复测；若发布流程依赖 Vite 入口，应单独修复或明确生产只使用 8000 静态入口。另有 AUDIT-009 的低风险质量门禁阻断。

## 13. 发布建议

**GO WITH RISKS**。8000 静态发布入口和已覆盖的国内/外网页面可继续验收；AUDIT-009 需在发布流水线中清理后再视为门禁通过。外网自动采集、自动聚合、自动告警评估、AI、通知和跨语言自动确认继续保持关闭。真实外网故障、事件告警详情（当前 `foreign_events=0`）和额外角色权限测试应在隔离测试环境完成，不得用生产写操作替代。

## 14. 下一阶段开发建议

1. **P0：补齐隔离样本。** 在独立测试库构造事件型外网告警，真实验证“告警标题 → 外网事件详情”；同时保留 `foreign_event_candidates=0`、`foreign_events=0` 的生产只读约束。
2. **P0：保持关闭高风险自动化。** 外网自动采集、自动事件、自动告警、AI、代理、外部通知和跨语言自动确认默认关闭，先完成审计与人工确认闭环。
3. **P1：建立外网依赖故障门禁。** 覆盖 DNS/TLS、HTTP 4xx/5xx、RSS/XML 异常、关键词/语言识别、URL 去重、超时、部分响应和网络恢复；测试必须隔离生产表。
4. **P1：增强事件证据。** 增加共同实体、时间差、来源列表、标题/摘要/正文相似度分解、语言组合和置信度解释字段，并在候选、人工确认和审计中复用。
5. **P1：采用分阶段跨语言策略。** 同语言高置信度候选可按现有门槛自动确认；跨语言仅生成 `pending` 候选并人工确认，积累标注样本后再评估自动确认。
6. **P1：扩充清洗回归集。** 为 HTML/NYT HTML 增加实体、URL、图片说明、script/style/iframe、事件属性和危险链接清洗测试，避免模板文本污染相似度。
7. **P2：统一告警处置契约。** 设计确认/解决/抑制弹窗、备注、幂等、非法状态拒绝、回滚和审计历史，并以隔离样本验证失败重试。
8. **P2：固化 CI 与隔离证据。** 将 `compileall`、前端构建、`git diff --check`、迁移升级/降级、国内数据快照前后对比和外网失败矩阵纳入发布门禁；清理 AUDIT-009 后再放行。
9. **架构边界：** 保持 foreign_* 服务、模型、配置和日志与国内 opinions/events/alerts/Dashboard/地图/热词/scheduler 隔离，不进入 Phase 6 自动化建设。

## 15. 证据索引

- `audit-evidence/AUDIT-BASE-dashboard.png`
- `audit-evidence/AUDIT-desktop-dashboard.png`
- `audit-evidence/AUDIT-mobile-dashboard.png`
- `audit-evidence/AUDIT-tablet-foreign.png`
- `audit-evidence/AUDIT-mobile-foreign.png`
- `audit-evidence/AUDIT-events-table-overflow.png`
- `audit-evidence/AUDIT-opinion-refresh-reset.png`
- `audit-evidence/AUDIT-auth-invalid.png`
- `audit-evidence/AUDIT-auth-logout.png`
- `audit-evidence/AUDIT-auth-protected-route.txt`
- `audit-evidence/RETEST-mobile-dashboard-fixed.png`
- `audit-evidence/RETEST-events-view-button.png`
- `audit-evidence/RETEST-role-labels-fixed.png`
- `audit-evidence/RETEST-foreign-detail-fixed.png`
- `audit-evidence/RETEST-alert-title-not-clickable.txt`
- `audit-evidence/AUDIT-auth-invalid.png`
- `audit-evidence/AUDIT-auth-logout.png`
- `audit-evidence/AUDIT-auth-protected-route.txt`
- `audit-evidence/AUDIT-vite-dev-server.txt`
- `audit-evidence/RETEST-alert-title-clickable.png`
- `audit-evidence/RETEST-mobile-foreign-alerts.png`
- `audit-evidence/RETEST-mobile-foreign-alerts-layout.txt`
- `audit-evidence/RETEST-browser-navigation-logout-20260810.txt`
- `audit-evidence/AUDIT-command-checks-20260810.txt`
- `audit-evidence/AUDIT-command-checks-20260810-rerun.txt`
