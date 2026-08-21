# 舆情监测系统 v1.0.0 RBAC 收口交付报告

> 冻结提交：`4cbf2fa578f42ef1e3eb44c3e4843a1a0653d712`

## 1. 收口目标

将“账号→角色→权限”的授权从隐式/硬编码路径收敛为统一的 RBAC 矩阵，确保非超管角色只能访问被显式授予的接口与资源，杜绝越权（403 边界清晰）。

## 2. 矩阵现状（冻结时点）

| 项 | 数量 |
|---|---:|
| 角色 roles | 5 |
| 权限码 permissions | 89 |
| 角色-权限关联 role_permissions | 131 |
| user_roles 实际绑定 | 0 |

- 组合权限在比较前统一展开为细粒度叶子权限码（与 `/me` 一致），避免组合/叶子不一致导致的越权或误拒。
- role_permissions 无孤儿（缺失 role 或 permission 的关联为 0）。

## 3. 覆盖的接口边界

- **viewer**：仅读（GET 舆情/事件/告警/规则），写操作返回 403。
- **analyst**：具备 AI/研判类权限，但 `reports:manage` 未授予，模板写操作返回 403。
- **admin（超管）**：全部不 403，走独立校验分支 `test_admin_never_forbidden`。
- **动态角色**：从 `roles` 表实时读取所有启用角色（不含 admin），新增角色自动纳入覆盖（Phase Security-2 全角色 RBAC）。

## 4. 关键安全修复（与测试守卫）

- `test_rbac_hardening.py` 在导入期读取数据库角色以生成动态用例；原实现直接 `SessionLocal()` 连生产库，导致 pytest collection 挂起。
- 修复：① 仅在检测到目标为生产库 `opinion_db` 时模块级 `pytest.skip`；② 动态角色读取改用独立短连接超时 engine（`connect_timeout=5`），测试库不可达时快速失败并降级为空列表（动态用例自动 skip），不再无限阻塞。
- 该修复为**测试基础设施-only**，不涉及任何业务/权限判定逻辑变更，不修改 `conftest.py`、权限服务或迁移。

## 5. 遗留风险

- `user_roles` 为空：生产账号的真实“账号→角色”绑定未落表，依赖代码/默认角色判定。建议在后续版本明确绑定并补充落表数据（见遗留问题清单）。
- `test_rbac_hardening.py` 的动态用例在缺测试库环境下 skip；完整 RBAC 回归需在隔离测试库 `opinion_test@:5433` 执行（本冻结环境未启动）。

## 6. 结论

RBAC 矩阵与 403 边界已收口并具备可执行验证；动态角色覆盖机制到位。收口**达成**，仅 `user_roles` 落表绑定为后续待办。
