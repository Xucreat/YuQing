# 舆情监测系统 权限体系重构架构设计（Phase Security-RBAC-Redesign-Plan）

> 阶段性质：**RBAC / Permission Redesign Architecture Planning（只读设计）**
> 范围：`backend/app`、`frontend/src`、`backend/alembic`、生产只读库 `127.0.0.1:5432/opinion_db`
> 约束：未修改任何源码 / 前端 / 数据库 / 迁移 / 权限数据 / 生产配置；所有数据库访问为 `SELECT`。
> 时间：2026-08-13
> 依据：在 `docs/Phase_Security-RBAC-Audit.md`（上一阶段只读审计）基础上，**重新复核源码 + 库事实**后给出设计，非直接采纳旧方案。

---

# 0. 复核结论与上一阶段审计纠错（AUDIT_CORRECTION）

本阶段对上一阶段审计的每一项关键结论重新取证（`permissions.py`、`dependencies.py`、`foreign_batch_review_permissions.py`、`app/api/*` 全量 grep、Roles.vue、usePermission.ts、生产库 `SELECT`）。**库事实 21 孤儿 / foreign 96% 仅 admin 可用 / 删除门禁倒挂 / analyst 缺 foreign:ai:review:read 等核心结论全部属实**。但有以下 4 处表述需修正：

| # | 上一阶段结论 | 实际事实（本阶段复核） | 修正说明 |
|---|---|---|---|
| C1 | "4 个组合 permission（`foreign:read`/`foreign:data:manage`/`foreign:analysis`/`foreign:alerts:manage`）均无人持有" | `COMPOSITE_PERMISSIONS`（`permissions.py:34-94`）实际有 **5 个组合键**：`ai:analyze` + 上述 4 个 `foreign:*`。`ai:analyze` **被 admin+analyst 持有且生效**（展开到 `domestic:ai:*`）。 | 组合 permission 总数是 **5**，其中 4 个 `foreign:*` 为孤儿、1 个 `ai:analyze` 有效。旧报告把 `ai:analyze` 单独算作"已使用"，数量口径不统一。 |
| C2 | "analyst 持有 `sources:write` 但 `admin_data_sources` 用 `require_admin` 使其失效" | 全量 grep `app/api`：**没有任何 `require_permission("sources:write")`**。数据源写接口只使用 `sources:read`（读）与 `require_admin`（写/测试/调度）。`sources:write`（domestic）是**幽灵权限**——被 analyst 持有，但全代码无任何端点校验它。 | `sources:write` 不是"被 require_admin 覆盖"，而是"从未被任何端点引用"。属更精确的死权限定义。 |
| C3 | §4.1/§4.4："foreign.py / domestic_ai_analysis.py / foreign_alerts.py 复核/启用/采集走**Service 层内联判定（非依赖注入），构成缺口**" | `decide_review`（`domestic_ai_analysis.py:585-622`）**确实在端点函数体内按动作校验** `reject/confirm/complete/read`（行 608-622，与 `is_superuser_user` 组合），权限**有被强制**；`foreign_alerts.py` 全部使用统一的 `require_permission(foreign:alerts:*)`，是干净的。仅 `foreign.py`/`domestic_ai_analysis.py` 的 `require_*_review_read` 是**自定义 router 级依赖**。 | 权限**未被漏检**（非安全缺口），问题是**非统一**：依赖注入点不集中在 `require_permission` 装饰器，grep 装饰器看不到，需读函数体才能审计。属**可审计性/一致性**问题，非安全漏洞。 |
| C4 | 隐含"外网复核权限完全无门禁" | `foreign:ai:review:read` 由 **viewer** 持有（库实测），`foreign:ai:review:complete` 由 admin+analyst+viewer 持有；`require_foreign_review_read`（`foreign.py:95-106`）与 `decide_review` 内联校验共同构成门禁。 | 外网复核对 viewer/analyst **部分可用**，并非"全靠 `*` 兜底"。旧报告 §3.3 已正确列出 viewer 持有 `foreign:ai:review:read`，此处与 §3.5 孤儿清单一致，无矛盾；修正的是"完全无门禁"的措辞。 |

**无 CRITICAL/HIGH 级事实错误**；C1–C4 均为口径/精确性修正，不改变"需重构"的总判断。

---

# 1. Executive Decision

```
当前权限体系状态：        MAJOR_REFACTOR（仍需重构，但属"目录损坏 +  Enforcement 不一致"，非模型根本错误）
是否存在权限过细：        PARTIALLY（外网/国内复核子域笛卡尔积过细；按钮级不过细）
是否存在 Permission Explosion： YES（83 权限、21 孤儿=25.3%、4 组合 permission 利用率 0%、foreign 44/46 仅 admin）
是否存在权限冲突：        YES（删除门禁倒挂、analyst 缺 keywords:write 与 foreign:ai:review:read、sources:write 幽灵权限）
是否存在前后端不一致：    YES（前端强制 events:read/alerts:read/propagation:read；后端 domestic 读仅登录）
是否存在高风险安全问题：  MEDIUM（domestic 读接口无 *:read 强制；full-confirm 等高风险的 Enforcement 链路非统一；tasks 结果无归属校验）
是否建议重构：            YES

推荐方案：
  Role → Permission（叶子，Enforcement 唯一事实源）
    + Capability（业务能力打包/Preset，仅配置 UI 与角色模板使用，不进入 Enforcement 链路）
    + 修复 4 个 foreign:* 组合 permission 死分支（真正授予角色）
    + 清理 21 孤儿中的"功能性缺口/死分支"类
    + 统一 domestic 读 Enforcement（补 *:read）
    + 引入 system_admin（非 * 的可审计管理员角色）
不引入：Capability 数据库实体、data_scope/ABAC、行级权限、角色继承。
```

> 若继续"新增功能 → 新增 permission → 新增 checkbox"模式：① 目录持续失控（已 25% 孤儿）；② 外网域锁死（非 admin 不可用）；③ analyst 反复漏配（如本次 keywords:write）；④ 权限不可审计（组合+`*` 双层）；⑤ 每加一个外网子功能重复死分支。

> **下一阶段先做什么**：先治理**权限目录与角色分配数据**（清孤儿缺口、修 foreign 组合死分支、补 analyst 缺失、引入 system_admin 并赋具体权限），再统一**后端读/写 Enforcement 契约**（补 `*:read`、把内联校验提升为 `require_permission`/`require_any_permission`、tasks 加归属），最后做**Capability 抽象 + 配置 UI**。理由：Enforcement 与 UI 都以 permission 目录为单一事实源，目录先干净 UI 才有意义（与上一阶段一致，本阶段复核后确认无误）。

---

# 2. Current Architecture（复核后）

```
User(is_superuser:bool, role:str, roles:M2M)
   │  主角色 user.role → Role(name) ；附加角色 user_roles（当前 0 行）
   ▼
Role(is_system, is_enabled)  ──M2M──▶  role_permissions  ──M2M──▶  Permission(code, resource, action, group)
   │                                                            │
   │  get_user_permissions:  superuser→["*"]；否则 主角色∪附加角色 权限并集，再 expand_permissions（组合展开）
   ▼
require_permission(leaf) / require_admin / 自定义 require_*_review_read（router 级）/ decide_review 内联（端点体）
```

| 机制 | 是否存在 | 证据 |
|---|---|---|
| ADMIN/`*` bypass | 是 | `permissions.py:22-24,116-117,156-157` |
| 角色继承 | 否 | `role.py` 无 parent 字段 |
| 组合 permission（展开） | 是，5 个 | `permissions.py:34-94`；`ai:analyze` 有效，4 个 `foreign:*` 孤儿 |
| 资源/行级/data_scope | 否 | 全为 `resource:action` 操作级 |
| 前端按钮权限 | 是 | `usePermission.ts` `hasPermission` → `v-if` |
| 后端 API 权限 | 是 | `require_permission`/`require_admin` |
| 后端 Service 内联 | 否（仅端点体内联，功能正确） | `domestic_ai_analysis.py:608-622` |

**库实测（本阶段 `audit-evidence/_rbac_redesign_extract.py`）**：roles=4（admin/analyst/viewer/游离`111`）；permissions=83；users=3（admin 超管 / 测试=analyst / 观察测试=viewer）；user_roles=0；role_permissions=85（admin 48 / analyst 28 / viewer 8 / 111 1）；orphan=21；foreign 权限 46 个中 44 个仅 admin 可用（仅 `foreign:ai:review:read`(viewer)、`foreign:ai:review:complete`(analyst+viewer) 非 admin）。

---

# 3. Current Permission Inventory

见 `audit-evidence/_rbac_redesign_extract.py` 输出（83 行 permissions 全表 + 每权限直接持有角色）。关键分布：
- 按 `group` 列已存在 **19 个分组**（用户管理/角色管理/权限管理/关键词管理/舆情管理/事件管理/预警管理/数据源/传播溯源/报告/审计/AI能力/外网风险/Foreign sources/Foreign alerts/Foreign events/外网 AI/国内 AI/Foreign combined）——这是现有 UI 已有的分组基础，Capability 可在此之上聚合为更粗的"业务能力"。
- orphan 21：`users:read/write/activate`、`roles:read/write/delete`、`keywords:write`、`audit_logs:read`、`login_logs:read`、`foreign:read`、`foreign:data:manage`、`foreign:analysis`、`foreign:alerts:manage`、`foreign:ai:batch:read/cancel`、`foreign:events:review:read/confirm`、`foreign:alerts:review:read/confirm`、`foreign:ai:full-confirm`、`foreign:ai:review:reject`。
- 幽灵（持有但无端点校验）：`sources:write`（domestic）、`ai:manage`、`foreign:events:write`、`foreign:sources:collect_all`（后三者需实施阶段二次确认，疑为未接入 Enforcement）。

---

# 4. Permission Explosion Analysis

| 指标 | 值 | 判断 |
|---|---|---|
| permission 总数 | 83 | — |
| orphan 占比 | 21/83 = 25.3% | **爆炸主因 1**：目录污染 |
| 组合 permission 有效利用率 | 1/5（`ai:analyze`）；`foreign:*` 0/4 | **爆炸主因 2**：简化手段失效→外网域只能靠 `*` |
| foreign 域非 admin 可用占比 | 2/46 | **爆炸主因 3**：外网功能交付但除 admin 外无人能用 |
| 复核子域笛卡尔积（events/alerts/ai × read/confirm/complete/reject） | ~16 个可收敛为 ≤6 | **爆炸主因 4**：拆分无业务区分度 |
| UI-only permission 占比 | 0%（前端无纯装饰权限） | 非爆炸源 |
| 仅 admin 持有的叶子权限 | ~40 | 多数合理（系统管理/外网），但因孤儿+死分支而"看起来爆炸" |

**结论 = YES，但爆炸性质是"目录与分配损坏"，不是"叶子权限绝对数量不可接受"。** 目标不是把 83 压到 30，而是：清孤儿、修死分支、合并复核子域、统一 Enforcement。预计叶子权限净变化很小（见 §8）。

---

# 5. Business Capability Model（业务能力模型）

从 23 个待审模块中甄别**真实独立业务能力**（不按 permission 名称，按业务语义）：

| # | 业务能力 | 谁用 | 能力类型 | 高风险动作 | 是否独立 Capability | 当前问题 |
|---|---|---|---|---|---|---|
| 1 | 舆情监测 | 全员 | read | 删除(高危) | 是（舆情查看/编辑/删除 三档） | 删除门禁倒挂 |
| 2 | 事件处置 | analyst/operator | read/write/operate | 删除(高危) | 是 | 删除=write，无独立 delete |
| 3 | 预警处置 | analyst | read/write/operate | 启用规则(中高) | 是 | — |
| 4 | 传播溯源 | 全员 | read | 无 | 是（只读） | 读仅登录 |
| 5 | 报告 | analyst | read/export/manage | 导出(中) | 是 | — |
| 6 | 关键词 | analyst/operator | read/write | 无 | 是 | analyst 缺 write(孤儿) |
| 7 | 数据源配置 | system_admin/operator | read/write | 测试/调度(高) | 是 | sources:write 幽灵 |
| 8 | 采集触发 | system_admin/operator | operate | 触发采集(高,基础设施) | 是（独立高风） | 仅 require_admin |
| 9 | AI 检索 | analyst | use | 无 | 是 | — |
| 10 | 国内 AI 研判+复核 | analyst | read/write/operate | 全量确认(高) | 是 | 复核子域过细 |
| 11 | 外网数据/事件/预警/风险/AI | analyst(修复后) | read/write/operate | 全量确认(高) | 是（外网运营，含子动作） | 96% 仅 admin |
| 12 | 用户管理 | system_admin | manage | 增删改/启停(高) | 是（系统） | 全 orphan→仅 `*` |
| 13 | 角色管理 | system_admin | manage | 删角色(高) | 是（系统） | 全 orphan→仅 `*` |
| 14 | 权限目录 | system_admin | read | 无 | 是（系统） | 仅 analyst 持有(信息暴露) |
| 15 | 审计/登录日志 | system_admin | read | 无 | 是（系统） | 全 orphan→仅 `*` |
| 16 | 后台任务结果 | 触发者 | read(归属) | 无 | 是（需 owner 校验） | 无归属校验 |

**甄别结论**：
- "国内 AI 复核"与"外网 AI 复核"是**同一业务能力（AI 人工复核）的两个数据域**，子对象（events/alerts/ai）的 read/confirm/reject 应合并为统一动作，不应按子对象拆 3 倍。
- "外网数据/事件/预警/风险"在业务上是**一个"外网运营"能力**的不同资源，可合并为一个 Capability 下的多资源权限，不必拆成 5 个 Capability。
- "传播溯源"是纯只读，不进写/管理域。
- "采集触发"与"数据源测试/调度"同属基础设施高风，归 system_admin/operator。

---

# 6. Capability Design Alternatives（Capability 到底是什么）

用户核心问题：Capability = 权限组 / 业务能力 / 权限包 / UI 抽象 / 数据库实体？

| 方案 | 描述 | 数据模型复杂度 | 安全性 | 可审计 | UI 易用 | 维护成本 | migration 风险 | 本项目是否推荐 |
|---|---|---|---|---|---|---|---|---|
| **1. Role→Permission；Capability 仅前端** | Capability 纯前端常量，后端不认识 | 零（无新表） | 后端仍以叶子为准，清晰 | 后端审计靠叶子，能力级需展开 | 好 | 低 | 零 | ✅ 可接受但 UI 映射散落前端 |
| **2. Role→Capability→Permission；Capability 是 DB 实体** | 新表 `capabilities`+`role_capabilities`+`capability_permissions` | 高（3 表） | 清晰但多一层 | 最好 | 好 | 高（需迁 role_permissions） | 高（破坏 `*`/expand，需重写 get_user_permissions） | ❌ 当前规模过度设计 |
| **3. Role→Permission；Capability=权限包/Preset（参考表，不在 Enforcement 链路）** | `capability_catalog`（参考表或小表，只读）映射 能力→叶子集；UI 用它批量勾选并展开成叶子写入 `role_permissions`；Enforcement 仍 100% 叶子 | 低（1 参考表或无表，可用代码常量） | **Enforcement 单一事实源=叶子，无歧义** | 后端审计=叶子（清晰）；能力级=查 catalog（可选） | 好 | 低 | 低（不改 role_permissions 结构） | ✅✅ **推荐** |

**推荐 = 方案 3（Capability 作为"权限包/Preset"，不进入 Enforcement 链路）。**
理由（结合项目约束"简单/稳定/易配置/后端边界清晰"）：
1. **Enforcement 单一事实源不漂移**：`require_permission(leaf)` 不变，`expand_permissions` 组合展开不变，`*` 不变。引入 Capability 实体（方案 2）会让"某角色能做什么"出现叶子+能力两层真相，反而更难审计。
2. **零 schema 风险**：现有 `role_permissions` 完全不动；Capability 目录可用代码常量（与现有 `COMPOSITE_PERMISSIONS` 同源）或一张只读 `capabilities` 参考表承载。
3. **复用现有组合机制**：4 个 `foreign:*` 组合 permission 本就是"能力→叶子"的映射，只需把它们从"孤儿"修复为"真正授予角色"即可，无需新机制。
4. **规模匹配**：本项目 5 角色 / 83 权限，方案 2 的复杂度不划算。

**Capability 不进入数据库作为 Enforcement 实体**；最多作为只读参考（catalog）供 UI 与角色模板消费。

---

# 7. Recommended Capability Architecture

```
User → Role (扁平, 可多角色并集, 沿用现状)
            │
            │  role_permissions（叶子 permission，Enforcement 唯一事实源，结构不变）
            ▼
        Permission(code=resource:action)
            ▲
            │  expand_permissions（组合 permission 展开，修复 4 个 foreign:* 后生效）
            │
   capability_catalog（参考：能力名 → 叶子集 + 高风险标记）  ← 仅配置 UI / 角色模板使用
            │
   Roles.vue：勾选 Capability → 展开叶子 → 写入 role_permissions
```

- **引入机制**：`capability_catalog`（代码常量，位于 `app/core/capabilities.py`，结构同 `COMPOSITE_PERMISSIONS` 但语义为"业务能力→叶子集"），前端经 `/capabilities` 接口或复用 `/permissions`+group 渲染。
- **不引入**：Capability 实体表、data_scope、行级、角色继承、`*` 用于普通角色。
- **高风险动作**：在 catalog 中标记 `high_risk=True`，UI 放进"高级权限"折叠区，且**不隐含**于普通 Capability（勾选"事件运营"不会偷偷获得"事件删除"）。

---

# 8. Permission Redesign（全 83 条重新分类）

分类口径：
- **A 保留独立**（含高风险）：Enforcement 中真实使用，需独立存在。
- **B 合并**：与同业务能力其他 permission 笛卡尔积，应收敛。
- **C 修复为可用组合/Capability 别名**：当前孤儿但应生效（修死分支）。
- **D 删除**：定义但无任何端点 Enforcement 且无业务需要（实施阶段二次确认）。
- **E 历史兼容**：保留别名以向后兼容（如 `ai:analyze` 组合）。
- **F 定义但 Enforcement 缺失/疑幽灵**：实施阶段须确认端点引用，否则转 D。
- **G API 需要但目录缺失**：当前无对应 permission（如 `opinions:delete`）。

> "当前角色持有"来自库实测；"API Enforcement"来自 `app/api` 全量 grep + `domestic_ai_analysis.py:608-622` 内联。

### 8.1 系统管理域（users/roles/permissions/logs）

| Permission | 持有角色(DB) | API Enforcement | 风险 | 建议 | 新归属 |
|---|---|---|---|---|---|
| users:read | 孤儿 | users.py:183 ✓ | 高 | A 保留，赋 system_admin | 用户管理 |
| users:write | 孤儿 | users.py:209 ✓ | 高 | A 保留，赋 system_admin | 用户管理 |
| users:activate | 孤儿 | users.py:391 ✓ | 高 | A 保留，赋 system_admin | 用户管理 |
| roles:read | 孤儿 | users.py:432 ✓ | 高 | A 保留，赋 system_admin | 角色管理 |
| roles:write | 孤儿 | users.py:455 ✓ | 高 | A 保留，赋 system_admin | 角色管理 |
| roles:delete | 孤儿 | users.py:527 ✓ | 高 | A 保留，赋 system_admin | 角色管理 |
| permissions:read | analyst | users.py:552 ✓ | 中 | A 保留；**analyst 不应持**，改赋 system_admin（避免信息暴露） | 权限目录 |
| audit_logs:read | 孤儿 | users.py:604 ✓ | 中 | A 保留，赋 system_admin | 日志审计 |
| login_logs:read | 孤儿 | users.py:568 ✓ | 中 | A 保留，赋 system_admin | 日志审计 |

### 8.2 国内核心域（opinions/events/alerts/propagation/reports/keywords/sources）

| Permission | 持有 | Enforcement | 风险 | 建议 | 新归属 |
|---|---|---|---|---|---|
| opinions:read | 111/analyst/viewer | opinions.py 仅登录 ❌ | 中 | A + **补 `require_permission`**（统一读） | 舆情查看 |
| opinions:write | analyst | opinions.py:338 ✓ | 中 | A 保留 | 舆情编辑 |
| **opinions:delete（G 新增）** | 无 | opinions.py:490 现 `require_admin` | 高 | G→A：新增叶子，替换 `require_admin`，赋 data_steward/system_admin | 舆情删除(高) |
| events:read | analyst/viewer | events.py 仅登录 ❌ | 中 | A + 补 `require_permission` | 事件查看 |
| events:write | analyst | events.py:132/349/414 ✓ | 中 | A 保留（含 confirm/merge/split/status/rebuild/close） | 事件运营 |
| **events:delete（G 新增）** | 无 | events.py:449 现 `events:write` | 高 | G→A：新增独立 delete，analyst 不再因 write 而能删 | 事件删除(高) |
| alerts:read | analyst/viewer | alerts.py 仅登录 ❌ | 中 | A + 补 `require_permission` | 预警查看 |
| alerts:write | analyst | alerts.py:56 ✓ | 中 | A 保留（acknowledge/resolve/suppress） | 预警处置 |
| **alerts:enable（独立高风）** | admin | foreign_alerts 疑未强制(F) | 中高 | A 保留并确认 Enforcement（启用规则） | 预警处置(高) |
| propagation:read | analyst/viewer | propagation.py 仅登录 ❌ | 低 | A + 补 `require_permission` | 传播溯源(只读) |
| reports:read | analyst | reports.py:66 ✓ | 低 | A 保留 | 报告 |
| reports:export | analyst | reports.py:77 ✓ | 中 | A 保留（导出独立） | 报告 |
| reports:manage | admin/analyst | reports.py:320 ✓ | 中 | A 保留 | 报告 |
| keywords:read | analyst | keywords.py:106 ✓ | 低 | A 保留 | 关键词 |
| keywords:write | 孤儿 | keywords.py:134 ✓ | 中 | **A 修复**：赋 analyst/operator（功能性缺口） | 关键词 |
| sources:read | analyst | admin_data_sources.py:879 ✓ | 低 | A 保留 | 数据源 |
| sources:write | analyst | **无端点引用(F 幽灵)** | 中 | F→D 删除（或接入数据源写 Enforcement 后再保留） | 数据源 |
| ai:search | admin/analyst | bocha.py:39/anspire.py:22 ✓ | 低 | A 保留 | AI检索 |
| ai:analyze | admin/analyst | analysis.py:46 ✓（且为组合键） | 中 | **E 保留为组合别名**（展开 domestic:ai:*） | 国内AI研判 |
| ai:manage | admin | **无端点引用(F 幽灵)** | 中 | F→D 删除（AI 配置若需，另立 permission） | (删) |

### 8.3 国内 AI 复核域（domestic:ai:*）

| Permission | 持有 | Enforcement | 风险 | 建议 | 新归属 |
|---|---|---|---|---|---|
| domestic:ai:analyze | admin/analyst | domestic_ai_analysis.py:332 ✓ | 中 | A 保留 | 国内AI研判 |
| domestic:ai:batch:read | admin/analyst | :427 ✓ | 低 | A 保留 | 国内AI研判 |
| domestic:ai:batch:cancel | admin/analyst | :474 ✓ | 中 | A 保留 | 国内AI研判 |
| domestic:ai:review:read | admin/analyst/viewer | :734 + 自定义dep ✓ | 低 | **B 合并**为 `domestic:review:read` | 国内AI复核 |
| domestic:events:review:read | admin/analyst | 自定义dep ✓ | 低 | **B 合并**为 `domestic:review:read` | 国内AI复核 |
| domestic:alerts:review:read | admin/analyst | 自定义dep ✓ | 低 | **B 合并**为 `domestic:review:read` | 国内AI复核 |
| domestic:events:review:confirm | admin/analyst | :614 内联 ✓ | 中 | **B 合并**为 `domestic:review:confirm` | 国内AI复核 |
| domestic:alerts:review:confirm | admin/analyst | :616 内联 ✓ | 中 | **B 合并**为 `domestic:review:confirm` | 国内AI复核 |
| domestic:ai:review:complete | admin/analyst/viewer | :618 内联 ✓ | 中 | **B 合并**为 `domestic:review:confirm` | 国内AI复核 |
| domestic:ai:review:reject | admin/analyst | :612 内联 ✓ | 中 | **B 合并**为 `domestic:review:reject` | 国内AI复核 |
| domestic:ai:full-confirm | admin/analyst | :? 内联(高风) | **高** | A 保留独立（全量确认） | 国内AI复核(高) |

→ 国内复核 11 个收敛为 `domestic:review:read` / `:confirm` / `:reject` + 保留 `domestic:ai:full-confirm`（高风）。**减 7 个。**

### 8.4 外网域（foreign:*，46 个）

| 子集 | 代表 permission | 持有 | Enforcement | 风险 | 建议 | 新归属 |
|---|---|---|---|---|---|---|
| foreign:opinions:read | admin | foreign.py:1014 ✓ | 低 | A 保留；修复后赋 analyst | 外网运营 |
| foreign:risk:* (5) | read/analyze/batch/ai/terms:read | admin | foreign.py:1853/1971/1989/2020/2090 ✓ | 中 | A 保留；赋 analyst | 外网运营 |
| foreign:events:read/candidates:read | admin | foreign_events.py:53/206 ✓ | 低 | A 保留；赋 analyst | 外网运营 |
| foreign:events:confirm/merge/split/status/rebuild/auto-aggregate (7) | admin | foreign_events.py:414/488/519/550/597/630 ✓ | 中 | A 保留（事件编辑，合并进"外网事件运营"） | 外网运营 |
| foreign:alerts:read/rules:read/rules:write/evaluate/acknowledge/resolve/suppress (8) | admin | foreign_alerts.py:46/447/465/245/316/359/402 ✓ | 中 | A 保留；赋 analyst | 外网运营 |
| foreign:alerts:enable | admin | **F 疑未强制** | 中高 | A 保留+确认 Enforcement | 外网运营(高) |
| foreign:alerts:ai-admit | admin | foreign.py:1198 ✓ | 中 | A 保留 | 外网运营 |
| foreign:keywords:read/write | admin | foreign.py:502/478 ✓ | 中 | A 保留；赋 analyst/operator | 外网运营 |
| foreign:sources:read/write/test | admin | foreign.py:649/699/875 ✓ | 中/高(test) | A 保留；赋 system_admin/operator | 外网运营/数据源 |
| foreign:sources:collect/collect_all | admin | collect ✓ / **collect_all F 疑幽灵** | 高 | A 保留 collect；collect_all F→D | 采集触发(高) |
| foreign:events:write | admin | **F 无引用** | 中 | F→D | (删) |
| foreign:ai:analyze | admin | foreign.py:1151/1409/1439 ✓ | 中 | A 保留；赋 analyst | 外网运营 |
| foreign:ai:batch:read/cancel | 孤儿 | foreign.py:1495/1534 ✓ | 低/中 | **C 修复**：赋 analyst/operator | 外网运营 |
| foreign:ai:review:read | viewer | foreign.py:95 自定义dep ✓ | 低 | **B 合并**为 `foreign:review:read` | 外网AI复核 |
| foreign:events:review:read/confirm | 孤儿 | 自定义dep/内联 ✓ | 低/中 | **B 合并**为 `foreign:review:read`/`:confirm` | 外网AI复核 |
| foreign:alerts:review:read/confirm | 孤儿 | 自定义dep/内联 ✓ | 低/中 | **B 合并**为 `foreign:review:read`/`:confirm` | 外网AI复核 |
| foreign:ai:review:complete | admin/analyst/viewer | 内联 ✓ | 中 | **B 合并**为 `foreign:review:confirm` | 外网AI复核 |
| foreign:ai:review:reject | 孤儿 | 内联 ✓ | 中 | **B 合并**为 `foreign:review:reject` | 外网AI复核 |
| foreign:ai:full-confirm | 孤儿 | 内联(高风) | **高** | A 保留独立 | 外网AI复核(高) |
| **组合 foreign:read** | 孤儿 | 展开 foreign:*:read 集 | 低 | **C 修复**：赋 analyst（外网查看能力） | 外网运营(Capability别名) |
| **组合 foreign:data:manage** | 孤儿 | 展开 foreign:*:write/test/collect | 中 | **C 修复**：赋 operator/system_admin | 外网运营(Capability别名) |
| **组合 foreign:analysis** | 孤儿 | 展开 foreign:* 分析+复核 | 中 | **C 修复**：赋 analyst（修复死分支） | 外网AI复核(Capability别名) |
| **组合 foreign:alerts:manage** | 孤儿 | 展开 foreign:alerts:* | 中 | **C 修复**：赋 analyst | 外网运营(Capability别名) |

→ 外网复核 9 个收敛为 `foreign:review:read`/`:confirm`/`:reject` + 保留 `foreign:ai:full-confirm`。**减 6 个。**

### 8.5 净变化估算

- 合并减：国内 7 + 外网 6 = **13**
- 新增（G）：`opinions:delete`、`events:delete` = **+2**（替换原 require_admin / events:write 隐含删除）
- 删除（D/F）：`sources:write`、`ai:manage`、`foreign:events:write`、`foreign:sources:collect_all` + 复核收敛释放的旧叶子（已计入减 13）= **约 −4**
- 保留组合：5（含 4 foreign:* 修复为可用）
- **预计叶子 permission：83 − 13 + 2 − 4 ≈ 68**（区间 65–75，取决于 F 类最终确认）。**数量未大幅压缩，但 0 孤儿、0 幽灵、foreign 可用。**
- **Capability 数量：约 16–20**（见 §10 矩阵）。
- **角色数量：5**（见 §10）。

> 关键立场：**本设计不追求"少 permission"，追求"语义清晰 + 无孤儿/幽灵 + Enforcement 一致 + 可审计"**。数量从 83→~70 是副产物，不是目标。

---

# 9. Domestic / Foreign Domain Strategy

候选：A 保留 `domestic:*`/`foreign:*` 前缀；B 统一 `events:*` + `data_scope`；C 统一 `events:*` + domain/source scope。

**推荐 = A（保留 domain 前缀），拒绝 B/C 的 data_scope。**

论证：
1. **代码现实已用前缀**：后端 `require_permission("foreign:events:read")` 与前端 `hasPermission("foreign:events:read")` 全量使用 `foreign:` 前缀（grep 证实）。改 data_scope 需改写每个端点 + 前端 + 引入 scope 解析层，风险极高、收益低。
2. **ABAC/data_scope 超出项目约束**：工作记忆明确"禁止引入复杂模型 / 行级权限本期不做"。domestic/foreign 是**架构隔离**（独立 router/service/model），不是"同资源不同数据范围"，用 data_scope 建模是错配。
3. **爆炸不在前缀**：爆炸来自"复核子域按 events/alerts/ai 拆 3 倍" + "组合死分支"。§8.3/§8.4 已通过合并复核子域 + 修复组合解决，无需动 domain 结构。
4. **保留前缀的可扩展性**：未来若真需"同一人管国内不管外网"，角色模板即可表达（analyst 赋 domestic 全套 + 外网部分），无需 scope 引擎。

→ **domestic / foreign 继续作为 permission domain 前缀；笛卡尔积通过"复核子域合并"消除，不通过 scope 系统。**

---

# 10. Role Redesign

角色应按**岗位职责**划分（非功能随意组合），避免角色爆炸。推荐 **5 个角色**：

| 角色 | 性质 | 职责 | 可访问模块 | 可执行的独立高风动作 | 不应拥有 | 划分依据 |
|---|---|---|---|---|---|---|
| **superuser（应急）** | `is_superuser`/`role=admin` → `*` | 初始部署/灾难恢复 | 全部 | 全部 | （仅应急，文档化边界） | 保留兼容 |
| **system_admin（系统管理员）** | 普通角色，持具体权限 | 日常运维 | 用户/角色/权限目录/日志/数据源/采集/系统配置 | users:*/roles:*/启用数据源/触发采集 | 业务研判/事件处置/外网内容编辑 | 让"系统管理"可审计（解除 `*` 锁定） |
| **analyst（分析员）** | 普通角色 | 业务分析+处置+外网运营 | 舆情/事件/预警/传播/报告/关键词/AI检索/国内AI研判/外网运营（修复后） | 删除舆情(若赋data_steward)/事件删除(若赋)/full-confirm | 用户/角色/权限管理 | 业务主角色 |
| **operator（采集员）** | 普通角色 | 数据源与采集 | 数据源(读写)/关键词/采集触发/采集日志/外网数据源 | 触发采集/测试数据源 | 事件处置/预警/AI研判/用户管理 | 基础设施岗位 |
| **viewer（只读）** | 普通角色 | 察看 | 全部 `:read` + 复核 read | 无 | 任何写/删/管理 | 只读 |

**关键设计点**：
- **不引入** event_operator/alert_operator/report_operator/foreign_analyst/auditor 等细分角色——会造成角色爆炸。需要"只看外网"等特例时，用角色模板微调（赋外网 Capability 子集）而非新建角色。
- **system_admin 解除 `*` 锁定**：持有 `users:*`/`roles:*`/`permissions:read`/`audit_logs:read`/`login_logs:read`/`sources:*`/`collector:run` 等**具体叶子**，全部可从 `role_permissions` 审计。
- **analyst 修复**：补 `keywords:write` + `foreign:analysis`（组合，修复死分支使其获得外网分析/复核全套）+ `foreign:ai:review:read`（修复"能 complete 不能 read"）。
- **游离角色 `111`**：清理（测试残留），并加角色创建约束（禁止非 system 角色随意建角色，或建后默认 viewer 权限）。
- **删除门禁**：analyst 经 `events:delete` 独立 permission 才删事件；舆情删除需 `opinions:delete`（赋 data_steward 或 system_admin），不再裸 `require_admin`。

**Role → Capability → Permission 矩阵（★=高风独立 permission）**：

| Capability | superuser | system_admin | analyst | operator | viewer |
|---|:--:|:--:|:--:|:--:|:--:|
| 舆情查看 | * | ✓ | ✓ | - | ✓ |
| 舆情编辑 | * | - | ✓ | - | - |
| 舆情删除★ | * | ✓ | (可选) | - | - |
| 事件查看 | * | ✓ | ✓ | - | ✓ |
| 事件运营 | * | - | ✓ | - | - |
| 事件删除★ | * | ✓ | (可选) | - | - |
| 预警查看 | * | ✓ | ✓ | - | ✓ |
| 预警处置(含启用★) | * | ✓ | ✓ | - | - |
| 传播溯源(只读) | * | ✓ | ✓ | - | ✓ |
| 报告(读/导出/管理) | * | ✓ | ✓ | - | - |
| 关键词 | * | ✓ | ✓ | ✓ | - |
| 数据源(读/写/测试★) | * | ✓ | - | ✓ | - |
| 采集触发★ | * | ✓ | - | ✓ | - |
| AI检索 | * | ✓ | ✓ | - | - |
| 国内AI研判+复核 | * | ✓ | ✓ | - | read |
| 外网运营(含事件/预警/风险/AI/数据) | * | ✓ | ✓ | ✓(数据源部分) | read |
| 外网AI复核(full-confirm★) | * | ✓ | ✓ | - | - |
| 用户管理★ | * | ✓ | - | - | - |
| 角色管理★ | * | ✓ | - | - | - |
| 权限目录 | * | ✓ | - | - | - |
| 日志审计 | * | ✓ | - | - | - |

（`*` = superuser 经 `*` 兜底；`(可选)` = 用角色模板微调，默认不赋）

---

# 11. Superuser Strategy

- **保留 `*` 仅作应急**：`is_superuser` 字段 + `role=='admin'` 仍映射 `*`（`permissions.py:22-24` 不变）。边界写进运维文档（初始部署 / 灾难恢复 / 紧急运维）。
- **`role=='admin'` 继续等价超管**（向后兼容），但日常运维改用 **system_admin** 角色。
- **system_admin 不持有 `*`**，持具体叶子 → 可从 `role_permissions` 审计"系统管理员能做什么"。
- **禁止普通角色依赖 `*`**：所有系统管理端点必须 `require_permission(具体码)`，已由 `users.py` 实现；引入 system_admin 后验证其能通过这些端点（实施阶段回归）。
- **最后超管保护**：保留 `users.py` 的 `_active_superuser_count` 防误删/停用最后一个超管。

---

# 12. Backend Enforcement Architecture

统一契约：

```
HTTP → get_current_user（认证）
        → 授权依赖（三选一，均在 router 装饰器可见）：
             require_permission(leaf)          # 普通写/管理/读（统一补 *:read）
             require_any_permission([...])     # 多码任一即放行（替代自定义 require_*_review_read）
             require_admin                      # 仅超管（基础设施/灾难）
        → Service（业务，不做权限判断；仅做 owner/scope 数据校验并显式注释）
```

- **统一读 Enforcement**：所有 list/detail/get 端点补 `require_permission("<res>:read")`（opinions/events/alerts/propagation/sources 等当前仅登录的）。不会破坏现有角色（它们已持 `:read`）。
- **消除自定义依赖**：`require_foreign_review_read`/`require_domestic_review_read` 改为 `require_any_permission([...review:read])`；`decide_review` 的内联按动作校验（行 608-622）提升为 `require_permission`/`require_any_permission` 装饰器（按 action 分流或用 `require_any_permission` 包住 confirm/reject/complete），使门禁对 grep 可见。
- **保留 `*`**：superuser 在 `require_permission` 内直接放行（`permissions.py:156-157` 不变）。
- **Service 层禁权限判断**：`report_template_service.py:68` 的 owner 校验是数据范围（合法），其余 Service 不得再判 `is_superuser`/`get_user_permissions`。
- **可审计契约**：新增 lint/测试，断言"所有 `@router.X(...,` 非 GET 或 GET 返回敏感数据 的端点，必须有 require_permission/require_admin/require_any_permission 之一"。
- **tasks 结果归属**：`tasks.py` 加 `current_user` 归属校验（仅本人或 system_admin/超管可读结果）。

---

# 13. Frontend Authorization Architecture

比较：A 前后端都直接用 permission；B 前后端用 Capability；C 前端 Capability、后端 Permission。

**推荐 = C 的精确版**：
- **后端 Enforcement 唯一事实源 = 叶子 permission**（不变）。前端 `hasPermission(leaf)` 继续用作 `v-if` 实际判断（与后端一致）。
- **Capability 仅用于 UI 分组与角色模板**：菜单/按钮按 Capability 归类展示；Roles.vue 勾选 Capability 时展开成叶子写入。前端不新增"Capability Enforcement"层（前端永远不是安全边界）。
- `usePermission.ts` 现有 `hasPermission`/`hasModulePermission`/`canAccessRoute` 保留；新增可选 `hasCapability(name)` 仅作 UI 分组便利（内部仍展开为叶子 `hasPermission`）。
- 路由守卫（`router/index.ts:161-183`）保持"体验层非安全边界"注释；`meta.permission`/`meta.module` 不变。

→ 安全边界始终在后端 `require_permission(leaf)`；前端 Capability 是可读性封装，不产生新信任边界。

---

# 14. Role Configuration UI Design（Roles.vue 重构）

现状：`Roles.vue` 按 `group` 列渲染 ~83 个 checkbox（行 224-229），`FOREIGN_LEGACY_GROUPS` 隐藏外网旧组（行 239）。已是分组但仍是叶子平铺。

重设计（不暴露 83 checkbox）：

```
角色编辑：[ 系统管理员 ▼ ]（角色模板：超管/系统管理员/分析员/采集员/只读）
├─ 舆情
│   ☑ 查看  ☑ 编辑  ☐ 删除(高风)
├─ 事件
│   ☑ 查看  ☑ 运营(确认/合并/状态)  ☐ 删除(高风)
├─ 预警
│   ☑ 查看  ☑ 处置(确认/解决/抑制)  ☐ 启用规则(高风)
├─ 传播 / 报告 / 关键词 / 数据源 / 采集 / AI检索 / 国内AI研判
│   ...
├─ 外网运营
│   ☑ 查看  ☑ 事件/预警/风险/AI运营  ☑ 复核(确认/驳回)  ☐ 全量确认(高风)  ☑ 采集
└─ 系统管理
    ☑ 用户管理 ☑ 角色管理 ☑ 权限目录 ☑ 日志
        └─ [高级权限](折叠)：delete / full-confirm / enable / test / collect
```

规则：
- 每个 Capability 显示**中文说明 + 影响的叶子 permission 数 + 是否含高风**。
- **高风 permission 不隐含**：勾"事件运营"不获得"事件删除"；删除/全量确认/启用/采集在折叠"高级权限"区，且勾选时弹确认。
- **无隐藏隐含权限**：展开预览显示"勾选后将写入以下 N 个 permission 码"。
- **角色模板**：5 个模板一键套用 + 微调；自定义角色默认 viewer 基线。
- 数据来源：`capability_catalog`（后端 `/capabilities` 或复用 `/permissions`+group），前端不再硬编码 83 码。

---

# 15. Old → New Permission Mapping（节选→全量见 §8）

| 当前 Permission | 类别 | 新归属 | 动作 |
|---|---|---|---|
| domestic:ai:review:read / events:review:read / alerts:review:read | B | `domestic:review:read` | 合并 |
| domestic:events:review:confirm / alerts:review:confirm / ai:review:complete | B | `domestic:review:confirm` | 合并 |
| domestic:ai:review:reject | B | `domestic:review:reject` | 合并 |
| foreign:ai:review:read / events:review:read / alerts:review:read | B | `foreign:review:read` | 合并 |
| foreign:events:review:confirm / alerts:review:confirm / ai:review:complete | B | `foreign:review:confirm` | 合并 |
| foreign:ai:review:reject | B | `foreign:review:reject` | 合并 |
| domestic:ai:full-confirm / foreign:ai:full-confirm | A | 保留独立(高风) | 保留 |
| foreign:read / data:manage / analysis / alerts:manage | C | 修复为可用组合(Capability别名) | 赋角色 |
| keywords:write | A | 修复赋 analyst/operator | 赋角色 |
| sources:write / ai:manage / foreign:events:write / foreign:sources:collect_all | F→D | 删除(确认无 Enforcement) | 删除 |
| opinions DELETE(require_admin) | G→A | `opinions:delete` | 新增 |
| events DELETE(events:write) | G→A | `events:delete` | 新增 |
| users:*/roles:*/audit_logs:read/login_logs:read/permissions:read | A | 赋 system_admin（解除 `*` 锁定） | 赋角色 |

---

# 16. Old → New Role Mapping

| 旧角色 | 现状 | 新角色 | 变化 |
|---|---|---|---|
| admin | `*` 超管，role_permissions 48 行形同虚设 | **superuser（应急）** + 日常用 system_admin | 日常运维移交 system_admin；admin 仅应急 |
| analyst | 28 行，缺 keywords:write、缺 foreign:ai:review:read、外网几乎不可用 | **analyst** | 补 keywords:write + foreign:analysis(组合) + foreign:ai:review:read；外网运营可用 |
| viewer | 8 行只读 | **viewer** | 不变（保留复核 read） |
| 111 | 游离测试角色，1 行 | **删除** | 清理 |
| （无） | — | **system_admin**（新增） | 持系统管理具体权限，可审计 |
| （无） | — | **operator**（新增） | 数据源/采集/关键词 |

---

# 17. Migration Strategy

1. **Phase D1 目录与分配治理（先做，零 Enforcement 改动）**：
   - 修复 `foreign_batch_review_permissions.py` 死分支：改为"向 analyst/system_admin/operator 直接授予 foreign 分析/复核叶子"（不再依赖 `foreign:analysis` 组合持有）；或直接把 4 个 `foreign:*` 组合赋给对应角色。
   - 赋 `keywords:write`→analyst/operator；赋 `foreign:ai:review:read`→analyst；赋 `users:*`/`roles:*`/`permissions:read`/`audit_logs:read`/`login_logs:read`→system_admin；赋 `foreign:ai:batch:*`→analyst/operator。
   - 清理游离角色 `111`。
   - 建 `system_admin`/`operator` 角色 + 角色模板种子。
2. **Phase D2 Enforcement 统一**：
   - 补 `opinions:read`/`events:read`/`alerts:read`/`propagation:read`/`sources:read` 到对应读端点。
   - 新增 `opinions:delete`/`events:delete` 叶子，替换 `require_admin`/隐含删除；赋 system_admin（及可选 analyst）。
   - `decide_review` 内联校验提升为 `require_permission`/`require_any_permission`；`require_*_review_read` 改为 `require_any_permission`。
   - `tasks.py` 加归属校验。
   - 删除 F 类幽灵权限（确认无引用后）。
3. **Phase D3 Capability 抽象 + UI**：
   - 加 `app/core/capabilities.py`（catalog）；`/capabilities` 接口。
   - Roles.vue 改为 Capability 三层 + 角色模板。
   - 合并国内/外网复核子域 permission（rename + 更新 `require_permission` 调用 + 前端 `hasPermission`）。
4. **Phase D4 回归 + 文档**：更新 `test_rbac*`；写《RBAC 运维手册》（superuser 边界、角色职责、命名规范 `resource:action`，禁止 `-` 作 action 分隔符）。

---

# 18. Permission Expansion Risk Analysis（迁移不得扩大低权限角色）

| 变更 | 受影响角色 | 权限扩大？ | 控制 |
|---|---|---|---|
| 赋 `foreign:analysis`(组合)→analyst | analyst | **扩大**（获外网分析/复核全套） | **预期且需审批**：analyst 本就应运营外网；若暂不想扩大，先只赋 `foreign:read`+`foreign:ai:review:read` |
| 赋 `keywords:write`→analyst | analyst | 扩大（可管关键词） | 预期（修复功能性缺口） |
| 赋 `users:*`→system_admin（新角色） | system_admin(新) | 新角色，不影响旧 | 新角色默认无成员，手动指派 |
| 合并复核子域→`foreign:review:read` | viewer | **缩小**（viewer 原持 foreign:ai:review:read；events/alerts review read 原为孤儿，无损失） | 安全 |
| 新增 `events:delete` 独立 | analyst | **缩小**（原因 events:write 可删 → 现需独立 delete，默认不赋） | 安全（去除隐含删除） |
| 补 `*:read` Enforcement | viewer/analyst | 无（已持 read） | 安全 |
| 删 `sources:write` 等幽灵 | analyst | **缩小**（去除无效权限） | 安全 |

**底线**：任何"合并/组合"类变更不得让 viewer/analyst 获得原无的写/删/系统权限；扩大仅发生在"analyst 获得应得的外网能力"且须显式审批。

---

# 19. Security Regression Matrix（实施后必须验证）

| 操作 | superuser | system_admin | analyst | operator | viewer | 原因 |
|---|:--:|:--:|:--:|:--:|:--:|---|
| read opinions/events/alerts/propagation | ✓ | ✓ | ✓ | - | ✓ | `:read` |
| write opinions/events/alerts | ✓ | - | ✓ | - | - | `:write` |
| delete opinions | ✓ | ✓ | (可选) | - | - | `opinions:delete` |
| delete events | ✓ | ✓ | (可选) | - | - | `events:delete` |
| manage events(confirm/merge) | ✓ | - | ✓ | - | - | `events:write` |
| manage alerts(ack/resolve) | ✓ | ✓ | ✓ | - | - | `alerts:write` |
| enable alert rules | ✓ | ✓ | ✓ | - | - | `alerts:enable` |
| manage keywords | ✓ | ✓ | ✓ | ✓ | - | `keywords:write` |
| manage sources/test | ✓ | ✓ | - | ✓ | - | `sources:write`(修复后) |
| trigger collector | ✓ | ✓ | - | ✓ | - | `collector:run` |
| AI analyze/search | ✓ | ✓ | ✓ | - | - | `ai:analyze`/`ai:search` |
| AI review(confirm/reject) | ✓ | ✓ | ✓ | - | - | `domestic/foreign:review:*` |
| AI full-confirm | ✓ | ✓ | ✓ | - | - | `*:full-confirm`(高风) |
| export reports | ✓ | ✓ | ✓ | - | - | `reports:export` |
| manage users/roles | ✓ | ✓ | - | - | - | `users:*`/`roles:*` |
| read audit/login logs | ✓ | ✓ | - | - | - | `*:logs:read` |
| read others' task results | ✓ | ✓ | - | - | - | owner/scope |

---

# 20. Implementation Phases

- **D1 目录与角色分配**（零 Enforcement 改动，最安全，先解"foreign 不可用/analyst 漏配"）：修复组合死分支、补 analyst 缺失、建 system_admin/operator、清 `111`。
- **D2 Enforcement 统一**：补 `*:read`、新增 `*:delete`、提升内联校验、tasks 归属、删幽灵。
- **D3 Capability + UI**：catalog、Roles.vue 三层、合并复核子域。
- **D4 回归 + 文档**。

---

# 21. Risks

1. **组合死分支修复需重跑授权**：赋组合/叶子后须验证 analyst 真能进外网（避免再次 0 行）。
2. **orphan 删除风险**：删 `sources:write` 等前须确证无端点引用（F 类），否则误删破坏现有 admin 写链路（`require_admin` 不受影响，但 habit 检查断裂）。
3. **`*` 依赖**：system_admin 必须能过所有系统管理 `require_permission(具体码)`；若某端点仍仅 `require_admin`，system_admin 会被卡（实施阶段回归）。
4. **合并复核子域的双写窗口**：rename permission 需同步改后端 `require_permission` + 前端 `hasPermission` + 组合表 `COMPOSITE_PERMISSIONS`，任一处遗漏即 403。
5. **角色创建无约束**：`111` 暴露可随意建角色；需加约束（默认 viewer 基线 / 仅 system_admin 可建）。
6. **前端 `/me` 缓存**：权限变更后需重登录或前端主动刷新（main.ts）。

---

# 22. Final Recommendation（回答 17 个核心问题）

1. **83 个 permission 是否过多？** 绝对值不极端；**问题在 25% 孤儿 + 外网 96% 仅 admin + 复核子域笛卡尔积**，非数量本身。
2. **真正的 explosion 是什么？** 目录污染（21 孤儿）+ 组合死分支（4 个 foreign:* 0 利用率）+ 外网锁死（44/46 仅 admin）+ 复核子域过细。
3. **正常细粒度是哪些？** 按钮/写/管理级（`opinions:write`、`events:write`、`reports:export`）——合理，保留。
4. **Capability 值得引入吗？** **值得，但作为"权限包/Preset"（方案 3），不引入 DB Enforcement 实体。**
5. **Capability 进数据库吗？** **不进 Enforcement 链路**；最多只读 catalog 参考表。
6. **国内/外网拆 domain 吗？** **保留 `domestic:`/`foreign:` 前缀**，不引入 data_scope（错配+超约束）。
7. **保留多少 permission？** 叶子 **~65–75**（净减约 10–15，主要来自复核合并+删幽灵+新增 delete）。
8. **保留多少 Capability？** **~16–20**（模块级业务能力）。
9. **保留多少角色？** **5**（superuser 应急 / system_admin / analyst / operator / viewer）。
10. **superuser/admin 怎么处理？** 保留 `*` 应急；日常用 **system_admin**（具体权限，可审计）；`role=admin` 仍等价超管兼容。
11. **避免"加按钮加 permission"？** ① 新动作先看是否属现有 Capability（合并进 `:write`/`:confirm`）；② 高风才立独立 permission；③ 角色模板覆盖常见组合；④ 新 permission 必须伴 Enforcement + 前端 + catalog 三处同步，否则 CI 报错。
12. **避免 Capability 再爆炸？** Capability 锁为模块级（~20 上限），子对象动作不升 Capability；复核子域已合并示范。
13. **后端 API 边界可审计？** 统一 `require_permission`/`require_any_permission`/`require_admin` 装饰器；新增 lint 断言"非 GET 或敏感 GET 必有授权依赖"；消除端点体内联。
14. **前端角色配置简单？** Roles.vue 改 Capability 三层 + 角色模板 + 高风折叠，不暴露叶子 checkbox。
15. **迁移不扩大低权限？** §18 矩阵：扩大仅限"analyst 获应得外网"，且显式审批；viewer/analyst 其余变更均为缩小或不变。

### 是否可进入下一阶段实施？
**可以。** 本设计为只读规划，所有结论基于 `permissions.py`/`dependencies.py`/`foreign_batch_review_permissions.py`/`app/api` 全量 grep / `Roles.vue` / `usePermission.ts` / 生产库 `SELECT`。下一阶段建议**从 D1（目录与角色分配）开始**，因其零 Enforcement 改动、风险最低、且直接解除"外网不可用 + analyst 漏配"两个最痛问题。

### 下一阶段拆分的 Phase
- **Phase D1**：权限目录与角色分配治理（修复组合死分支、补 analyst 缺失、建 system_admin/operator、清 `111`）。
- **Phase D2**：后端 Enforcement 统一（补 `*:read`、新增 `*:delete`、提升内联校验、tasks 归属、删幽灵）。
- **Phase D3**：Capability 抽象 + 配置 UI（catalog、Roles.vue 三层、合并复核子域）。
- **Phase D4**：回归测试 + 《RBAC 运维手册》。

---

> 本报告全部基于只读检查与生产只读库 `SELECT`，未对任何源码、数据库、迁移、权限数据或生产配置做修改。复核脚本：`audit-evidence/_rbac_redesign_extract.py`。
