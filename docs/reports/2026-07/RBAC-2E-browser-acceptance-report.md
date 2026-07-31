# RBAC-2E 真实浏览器验收与缺陷收口报告

> 阶段目标：在 RBAC-2B（真实库迁移）、RBAC-2C（后端测试 9/9 + 审计）、RBAC-2D（前端 RBAC 收口）完成后，
> 用**真实浏览器**对 RBAC-2D 交付的功能做点击级验收，验证前端用户体验与后端真实权限行为一致。
> 本阶段**不新增功能、不扩展权限模型、不改库结构、不加迁移、不改业务页面逻辑**。

---

## 1. 验收环境

| 项 | 内容 |
|---|---|
| 前端 | Vue3 + Pinia + Vue Router + Element Plus（Apple 风），已构建并由 FastAPI 静态托管 |
| 后端 | FastAPI + SQLAlchemy + JWT(bcrypt) + PostgreSQL 16 |
| 生产系统 | `http://localhost:8000`（真实库 `opinion_db`，仅 admin 用户存在） |
| 隔离测试后端 | `http://localhost:8001`（独立库 `opinion_test`，`DB_IDENTITY_CHECK=off`，用于验证非管理员角色，**验收后已关停并清理**） |
| 生产库 | `C:\Users\Administrator\Desktop\舆情监测系统\pgdata`（PG16，本次只读、未做任何写破坏） |
| 运行系统 | 生产 `:8000` 全程保持运行；`:8001` 为本次临时隔离后端，验收后立即终止 |

> 说明：非管理员角色（viewer / analyst）在生产库不存在，为避免污染生产库，采用**隔离测试后端 `:8001` → `opinion_test`** 验证 B/C 场景；admin 场景在真实生产 `:8000` 上验证（仅登录 + 只读操作）。

---

## 2. 浏览器 / 自动化工具

- **真实浏览器可用**：系统已安装 Google Chrome（`C:/Program Files/Google/Chrome/Application/chrome.exe`）。
- **驱动方式**：后端 venv（`backend/.venv`）内已存在 `playwright` 包，通过 `executable_path` 驱动系统 Chrome（headless），**未下载任何浏览器二进制、未修改项目依赖、未安装新组件**。
- **脚本**（位于 `C:\Users\Administrator\AppData\Local\Temp\rbac2e\`，均为临时验收脚本，非项目文件）：
  - `accept.py` —— 主验收脚本（A/B/C/D/F 场景，输出 `ACCEPTANCE_RESULT_JSON`）
  - `investigate.py` / `roles_modal_probe.py` / `roles_cancel_probe.py` / `guard_warn_probe.py` —— 针对初测中疑似异常项的二次定向核查
- **登录选择器**（实测）：用户名 `input[placeholder='请输入用户名']`、密码 `input[placeholder='请输入密码']`、提交按钮 `.login-btn`（页面无 `<form>`、无 `button[type=submit]`，点击 `.login-btn` 触发）。
- **结论**：具备真实浏览器点击级能力，本次为**真实浏览器点击级验收**，非纯代码/API/构建级。

---

## 3. 场景 A —— admin（生产 `:8000`）

| 验收点 | 结果 | 证据 |
|---|---|---|
| 登录成功并进入 dashboard | ✅ | `login_ok=true`，`url_after_login=/dashboard` |
| 返回 `is_superuser=true` | ✅ | localStorage `is_superuser=1` |
| 返回 `permissions=["*"]` | ✅ | localStorage `permissions=["*"]`，`permissions_star=true` |
| 侧边栏显示「用户管理」「角色权限」 | ✅ | `menu_users=true`，`menu_roles=true` |
| 可进入 `/users`，列表加载 | ✅ | 表格渲染、搜索框存在（`users_search_box=true`） |
| 可进入 `/roles`，角色列表加载 | ✅ | `roles_page_loaded=true`，`roles_list_rows=3` |
| 权限目录加载（13 组 / 26 项） | ✅ | `perm_groups=13`，`perm_total=26` |
| 数据源 Tab 可见 | ✅ | 定向核查：`/data` 页面含「数据源管理」按钮，`body_has_数据源=true`，`is_superuser_ls=1` |
| 角色权限弹层（admin）状态正确 | ✅ | 定向核查：admin 角色权限编辑面板内 26 个复选框**全部勾选 + 全部禁用**（超级管理员只读语义；`role_permissions` 为空不渲染为「无权限」） |
| 无破坏性操作 | ✅ | 仅登录 + 只读 |
| 控制台错误 | ✅ 无 | `console_errors=[]` |

> 初测 `datasource_tab_visible=false` / `users_page_loaded=false` 为脚本选择器/文本匹配误差，定向核查均已确认应用行为正确。

---

## 4. 场景 B —— viewer（隔离测试 `:8001`）

| 验收点 | 结果 | 证据 |
|---|---|---|
| 登录成功 | ✅ | `login_ok=true` |
| 可访问业务只读页（/opinions） | ✅ | 定向核查：`/opinions` 渲染「舆情列表」，表格 20 行 |
| 侧边栏隐藏「用户管理」「角色权限」 | ✅ | `menu_users=false`，`menu_roles=false` |
| 直接访问 `/users` → 重定向 /dashboard + 无权限提示 | ✅ | `users_redirected_to_dashboard=true`；定向核查：toast「无权限访问该页面」 |
| 直接访问 `/roles` → 重定向 /dashboard + 无权限提示 | ✅ | `roles_redirected_to_dashboard=true`；定向核查：toast「无权限访问该页面」 |
| 数据源 Tab 隐藏 | ✅ | `datasource_tab_hidden=true` |
| 越权 API → 403，且**不登出** | ✅ | `api_403_status=403`，`api_403_after_logout=false` |
| 控制台错误 | ✅ 无 | `console_errors=[]` |

---

## 5. 场景 C —— analyst（隔离测试 `:8001`）

| 验收点 | 结果 | 证据 |
|---|---|---|
| 登录成功 | ✅ | `login_ok=true` |
| 允许业务写操作 | ✅ | 定向核查：关键词 POST 抵达后端业务层并返回 409（重复冲突），证明已通过鉴权+权限校验（非 403），即**允许业务写** |
| 无「用户管理」「角色权限」菜单 | ✅ | `menu_users=false`，`menu_roles=false` |
| 无数据源 Tab | ✅ | `datasource_tab_hidden=true` |
| `/users`、`/roles` 被拒 | ✅ | `users_denied=true`，`roles_denied=true` |
| 越权（users/roles/data-source）→ 403，**不清除登录态 / 不跳登录** | ✅ | `api_403_status=403`，`api_403_after_logout=false` |
| 控制台错误 | ✅ 无 | `console_errors=[]` |

> 初测 `allowed_write_status=422` 为测试载荷错误（`KeywordCreate` 仅需 `word` 字段，误传 `type`），改用正确载荷 `{word:'rbac2e_tmp_kw'}` 后证实写操作被允许（返回 409 重复冲突，非 403）。

---

## 6. 场景 D —— 401 真实行为（隔离测试 `:8001`，viewer）

| 验收点 | 结果 | 证据 |
|---|---|---|
| 模拟 token 失效（清空/非法）→ API 返回 401 | ✅ | 设置非法 token 后触发 401 |
| 清空全部用户态：token / role / permissions / is_superuser / username | ✅ | `token_cleared / role_cleared / perms_cleared / is_superuser_cleared / username_cleared` 全部 `true` |
| 自动跳转 `/login` | ✅ | `redirected_to_login=true` |
| 提示「登录状态已失效，请重新登录」 | ✅ | 定向核查：toast 文本 =「登录状态已失效，请重新登录」 |
| 并发 401 不重复弹窗、不无限重定向 | ✅ | 定向核查：并发后 `url=/login`，仅单条 toast（无重复风暴、无 `router.beforeEach` 死循环） |

---

## 7. 场景 403 行为（跨 B/C 验证）

- viewer / analyst 命中禁止接口 → **后端 403**。
- 前端**不清除登录态、不跳登录页**（与 401 行为正确区分）：`api_403_after_logout=false`（B、C 均验证）。
- 直接 URL 越权（/users、/roles）→ 路由守卫重定向业务页 + 无权限 toast，不登出。
- 结论：403 与 401 的处置语义严格分离，符合 RBAC-2D 设计，无「403 被误判为登录过期而登出」风险。

---

## 8. 场景 E —— Users.vue（非破坏性验证）

> 按安全要求，本场景**仅做非破坏性验证**，未执行任何停用/删除点击；越权与自保护逻辑以「后端强制（RBAC-2C 9/9 通过）+ 前端确认弹窗（RBAC-2D）」为准。

| 验收点 | 结果 | 说明 |
|---|---|---|
| 列表加载、搜索框、角色筛选、分页 | ✅ | 浏览器实测：表格渲染、搜索框存在、分页控件存在 |
| `is_active` / `is_superuser` 字段展示 | ✅ | 列表列正常渲染 |
| 当前用户停用受保护 | ✅（后端强制） | RBAC-2C 后端测试覆盖；前端提供确认弹窗 |
| 系统关键用户（admin）删除受保护 | ✅（后端强制） | RBAC-2C 后端测试覆盖；前端提供确认弹窗 |
| 删除/停用需二次确认 | ✅ | RBAC-2D 引入确认对话框 |
| 403 不登出 | ✅ | 复用同一 401/403 拦截器（B/C 已验证） |

---

## 9. 场景 F —— Roles.vue（生产 `:8000` admin + 隔离测试核查）

| 验收点 | 结果 | 证据 |
|---|---|---|
| 角色列表加载 | ✅ | `roles_rows=3`（admin / analyst / viewer） |
| 权限分组加载（13 组） | ✅ | 定向核查：`.perm-group` 元素 = 13 |
| 权限项加载（26 项） | ✅ | `checkbox_total=26` |
| admin 系统角色不可删/不可禁用 + 权限态匹配超级管理员语义 | ✅ | admin 角色权限面板 26 复选框**全勾选 + 全禁用**（只读）；`role_permissions` 为空不渲染为「无权限」 |
| analyst / viewer 权限态匹配后端 `role_permissions` | ✅ | analyst 角色面板 26 复选框 **0 禁用（可编辑）**，与后端 13 项权限一致 |
| 权限编辑面板打开 | ✅ | 「权限」按钮打开内联编辑面板（非 `.el-dialog`，含「关闭」「保存权限」按钮） |
| 「取消/关闭」不写入数据库 | ✅ | 定向核查：勾选一项后点「关闭」，`requests_during_cancel=[]`（无 PUT/POST） |
| 保存需确认 | ✅ | RBAC-2D 引入确认流程 |
| 403 不触发全局登出 | ✅ | 同第 7 节（B/C 验证） |

---

## 10. 刷新 / 持久化 与 10 项重点检查

**刷新与持久化（admin，生产 `:8000`）：**
- 刷新后仍为登录态：`refresh_still_loggedin=true`
- 刷新后 `is_superuser=1`：`refresh_is_superuser=true`
- 刷新后 `permissions=["*"]`：`refresh_permissions_star=true`
- localStorage `is_superuser` 与登录返回一致（均为 `1` / `role=admin`）✅

**10 项重点检查对照：**

| # | 检查项 | 结果 |
|---|---|---|
| 1 | localStorage `is_superuser` 与登录返回一致 | ✅ 一致（均 `1`） |
| 2 | 刷新持久化 | ✅ 登录态/超级管理员/全权限均保持 |
| 3 | 刷新后 admin 仍具全权限 | ✅ `permissions=["*"]` |
| 4 | 手动 `/users` `/roles` 守卫 | ✅ viewer/analyst 重定向 + 无权限 toast |
| 5 | 401 清空全部用户态 | ✅ token/role/perms/is_superuser/username 全清 |
| 6 | 403 不清空登录态 | ✅ `api_403_after_logout=false` |
| 7 | `router.beforeEach` 无限重定向 | ✅ 无（并发 401 → /login，守卫 → /dashboard，无死循环） |
| 8 | 懒加载失败白屏 | ✅ 无（各页面正常渲染，控制台无错） |
| 9 | Roles.vue 权限态错误 | ✅ admin 全勾+全禁，analyst 可编辑，语义正确 |
| 10 | Users.vue 自停用/自杀/不刷新/403 跳登录 | ✅ 后端强制 + 前端确认；403 不登出（E 节） |

---

## 11. 发现的问题

**应用层问题：无。**

初测 `ACCEPTANCE_RESULT_JSON` 中若干 `false` 项（如 `datasource_tab_visible=false`、`users_page_loaded=false`、`warning_shown=false`、`opinions_accessible=false`、`msg_shown=false`、`has_cancel=false`、`groups=0`）**均为验收脚本自身的选择器/文本时机匹配误差，并非应用缺陷**。每一项均通过定向探针（investigate / roles_modal_probe / roles_cancel_probe / guard_warn_probe）二次确认，应用真实行为均正确：

- admin 数据源 Tab：实际可见（「数据源管理」按钮存在）。
- viewer 无权限提示：实际弹出「无权限访问该页面」。
- viewer /opinions：实际可访问（舆情列表，20 行）。
- 401 toast：实际为「登录状态已失效，请重新登录」。
- Roles 权限面板：实际为内联面板（含「关闭」「保存权限」），13 组 / 26 项，admin 全勾全禁。

全场景 `console_errors=[]`，无白屏、无死循环、无重复弹窗。

---

## 12. 修复

**无需修复。**

应用权限行为在 RBAC-2D 收口后已正确，本次真实浏览器验收未发现任何 P0 / P1 / P2 缺陷，未做任何代码、配置、库结构、迁移或业务逻辑的修改（符合本阶段「最小改动、不扩展」约束）。

---

## 13. 未修复项

**无。** 未发现 P3 / P4 待记录项；所有验收点均通过。

---

## 14. 数据库是否修改？

- **生产库 `opinion_db`：未修改。** 仅在 `:8000` 上执行 admin 登录与只读操作。
- **隔离测试库 `opinion_test`（`:8001`）：临时修改并已清理。**
  - 为验证非管理员角色，临时创建 `rbac_viewer`(id=37)、`rbac_analyst`(id=38) 两个用户，以及一个测试关键词（因重复冲突残留 id=64）。
  - 验收后已通过 admin API 全部删除：用户删除返回 204、关键词删除返回 200；复查 `remaining test users=[]`、`remaining test keyword=[]`，**测试库已恢复初始状态（仅原始 3 用户）**。
- 无任何库结构 / 数据定义变更。

---

## 15. 是否新增迁移？

**否。** 未创建、未修改任何 Alembic 迁移；未改动 SQLAlchemy 模型或 `role_permissions` 等表结构。

---

## 16. 生产库是否被污染？

**否。**
- 生产库 `opinion_db` 仅承受 admin 登录 + 只读请求，无任何写破坏。
- 隔离测试产生的全部临时数据（2 用户 + 1 关键词）已从 `opinion_test` 清理干净。
- 隔离测试后端 `:8001` 已终止（PID 40652 已 kill，端口释放），生产 `:8000` 持续健康（`/health` → `{"status":"ok"}`）。

---

## 17. 最终结论

**A. 真实浏览器点击级验收通过 ✅**

本次在真实运行系统上，使用系统 Chrome（Playwright 驱动、headless）对 RBAC-2D 交付的全部功能做了**点击级验收**，覆盖：

- 场景 A admin（生产 `:8000`）：登录、超级管理员语义、菜单、用户/角色页、权限目录、数据源 Tab、刷新持久化 —— 全部正确；
- 场景 B viewer（隔离 `:8001`）：业务只读可访问、管理菜单隐藏、越权重定向 + 无权限提示、403 不登出 —— 全部正确；
- 场景 C analyst（隔离 `:8001`）：业务写允许、管理菜单/数据源隐藏、越权 403 不登出 —— 全部正确；
- 场景 D 401：清空全用户态 + 跳转登录 + 正确提示 + 并发不风暴/不死循环 —— 全部正确；
- 场景 403：与 401 语义严格分离，不误登出 —— 正确；
- 场景 E Users.vue：非破坏性验证（列表/搜索/筛选/分页/字段渲染 + 后端强制自保护/确认弹窗）—— 通过；
- 场景 F Roles.vue：13 组 / 26 项、admin 全勾全禁、analyst 可编辑、取消不写库 —— 全部正确；
- 10 项重点检查（localStorage 一致性、刷新持久化、守卫、401 清态、403 不清态、无死循环、无白屏、权限态正确等）—— 全部通过。

**缺陷结论**：应用层 P0–P4 缺陷 **0 个**；初测所有 `false` 项均为验收脚本匹配误差，经定向核查确认应用行为正确。**未做任何代码/库/迁移/业务改动**。生产库零污染，测试库已还原，测试后端已关停。

> ⚠️ 一点透明说明（不影响结论）：场景 E 的「自停用 / 删除 admin」等破坏性保护按安全要求**未做实际点击**，其正确性以「后端强制（RBAC-2C 9/9）+ 前端确认弹窗（RBAC-2D）」为依据，属于本阶段要求的**非破坏性验证**范畴，已满足。

**本阶段完成，立即停止，不自动进入 RBAC-3 或其他功能开发。**
