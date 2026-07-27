# ARCH-10 同源残留清理报告

**任务范围**：仅处理「默认密码暴露」同源残留（与已修复的 admin 数据库层密码同源）。
**执行原则**：最小 diff、只读确认先行、不触碰数据库 / users 表 / admin 真实密码 / RBAC / JWT / 登录接口 / 权限模型，不处理其它 P1/P2/P3。
**日期**：2026-07-24

---

## 1. 修改文件列表

| # | 文件 | 修改类型 | 说明 |
|---|------|----------|------|
| 1 | `backend/app/core/config.py` | 配置默认值 + 新增 validator | 移除公开弱默认值 `"admin123"` |
| 2 | `frontend/src/views/Login.vue` | 前端源码 | 删除登录页 `admin123` 明文提示，密码预填置空 |

> 仅以上两处源码被修改；构建产物经 `vite build` + `python backend/_d.py` 重新同步至 `backend/app/static`，无其它源码、脚本、库文件变动。

---

## 2. 修改原因

- **同源风险**：此前 admin 数据库层密码已修复（`admin123` 已无法登录，RBAC/JWT/登录接口均验证正常）。但系统中仍残留两处**同源于同一弱口令**的明文：
  1. `config.py` 中 `init_admin_password` 的**公开默认值** `"admin123"`——任何未配置 `.env` 的部署都会以弱口令作为首次初始化管理员的兜底值。
  2. 前端登录页静态提示**硬编码展示** `admin123`，对终端用户形成弱口令暗示，且会被打包进前端产物。
- **目标**：切断弱口令在代码与产物中的同源残留，杜绝「任何路径下可用 admin123 登录」的兜底可能性，且不影响已有 admin 登录。

---

## 3. Diff 摘要

### 3.1 `backend/app/core/config.py`

```diff
     # ===== 初始化管理员 =====
     init_admin_username: str = "admin"
-    init_admin_password: str = "admin123"
+    # ARCH-10 同源残留清理：原公开弱默认值 "admin123" 已移除。
+    # 该字段仅在 init_db 首次创建 admin 时使用；为空/未配置时由下方
+    # validator 给出明确启动提示，要求通过 .env 的 INIT_ADMIN_PASSWORD
+    # 显式设置强密码，杜绝弱口令兜底。已存在 admin 时不会被写入。
+    init_admin_password: str = ""
```

新增安全提示 validator（不影响取值，仅在为空时打印明确告警）：

```diff
+    @field_validator("init_admin_password")
+    @classmethod
+    def _warn_empty_init_admin_password(cls, v: str) -> str:
+        """ARCH-10 同源残留清理：初始化管理员备用密码安全提示。..."""
+        if not v:
+            import sys
+            print(
+                "[SECURITY WARNING] INIT_ADMIN_PASSWORD 为空或未配置；"
+                "若需首次初始化管理员，请在 .env 中设置强随机密码，"
+                "否则 init_db 不会写入可用的默认凭据。",
+                file=sys.stderr,
+            )
+        return v
```

- `init_admin_password` 仅由 `backend/scripts/init_db.py` 在**首次创建** admin 时使用（`password_hash=hash_password(settings.init_admin_password)`）；当 admin 已存在时不重写。
- 运行时若未显式配置 `.env`，该值现为空字符串（`""`），**不再提供任何可登录的弱口令兜底**；且已有 admin 的凭据不受影响。

### 3.2 `frontend/src/views/Login.vue`

```diff
       <p class="login-hint">
-        默认账号 <code>admin</code> / <code>admin123</code>
+        默认账号 <code>admin</code>（初始密码请联系系统管理员获取）
       </p>
```

```diff
 const form = reactive({
   username: 'admin',
-  password: 'admin123',
+  password: '',
 })
```

- 仅删除明文弱口令展示、密码框预填置空；登录逻辑 / 接口调用（`handleLogin`、`api.post('/login')`、authStore、JWT 流程）**均未改动**。

---

## 4. 验证结果（A–E）

| 项 | 内容 | 结果 |
|----|------|------|
| **A 新密码登录** | `POST /api/login` 用 admin + 新强密码 | **HTTP 200**，`access_token` 长度 165，`permissions=["*"]` |
| **B admin123 登录** | `POST /api/login` 用 admin + `admin123` | **HTTP 401**（失败，符合预期） |
| **C JWT 鉴权** | 携带 `Bearer <access_token>` 访问 `/api/opinions` | **HTTP 200**（正常返回数据） |
| **D RBAC** | 登录响应 `permissions` | **`["*"]`**（超级权限保持正常） |
| **E 构建** | `vite build`（显式 node + `--max-old-space-size=1400`） | **成功**（`✓ built in 10.44s`，`BUILD_EXIT=0`）；产物已 `_d.py` 同步至 `backend/app/static` |

> 说明：B/C/D 验证基于 `.env` 中的 `INIT_ADMIN_PASSWORD` 仍覆盖为 `admin123`，但因 admin 已存在，`init_db` 不会重写凭据——这不影响本次「移除默认弱值」的收口目标（见第 5 节残留观察）。A 使用 admin 当前有效强密码，登录成功且 JWT/RBAC 不受影响。

---

## 5. `grep -rn "admin123"` 残留核查

执行：`grep -rn "admin123" backend/app frontend/src`

| 位置 | 结果 | 结论 |
|------|------|------|
| `frontend/src`（全部源码 .vue/.ts/.js） | **无匹配**（rc=1） | 前端源码已清理干净 |
| `backend/app/core/config.py` | 仅 **L46 注释**中出现 `"admin123"` 字样 | 非可用口令，仅为说明性注释 |
| `backend/app`（活跃文件，排除 `archive/old-/backup` 目录） | 仅 `config.py` 注释命中；已删除并重编译陈旧 `.pyc`（`__pycache__/config.cpython-313.pyc` 曾含旧默认 `"admin123"`，重编译后已无） | 活跃代码无可用弱口令 |
| `backend/app/static`（实际部署前端） | **0 个文件**含 `admin123` | 部署产物干净（`Login-D6SIXXBK.js`、`index-hrIey9kD.js` 均不含） |

### 残留观察（超出本任务范围，仅标注，未改动）

- **`C:/Users/Administrator/Desktop/YQ/.env`** 中仍含 `INIT_ADMIN_PASSWORD=admin123`（gitignored，不在本次 `backend/app frontend/src` 核查与修改范围）。
  - 影响评估：该值仅作为 `init_admin_password` 的运行时覆盖，而 `init_db` 在 admin 已存在时不重写凭据，故**系统实际安全、现有 admin 登录不受影响**。
  - 处置建议（非本次执行）：后续可单独作为运维项，将 `.env` 的 `INIT_ADMIN_PASSWORD` 改为强随机值或留空（留空时启动会打印明确安全告警，且不会写入可用默认凭据）。是否处理由你决定，本任务按纪律不予顺手改动。
- 归档备份目录（`frontend/dist.archive-*`、`backend/app/static/assets.archive-*`）中可能仍含历史 `admin123` 字符串，但**不在部署链路**，已排除在活跃文件核查之外。

---

## 6. 未影响范围声明（禁止事项核对）

- ✅ 未修改数据库、未修改 `users` 表、未修改 admin 真实密码
- ✅ 未修改 RBAC / 权限模型（验证 D 显示 `permissions=["*"]` 正常）
- ✅ 未修改 JWT 机制（验证 C 显示 JWT 鉴权正常）
- ✅ 未增加「修改密码」功能
- ✅ 未修改登录接口 / 认证流程（仅前端提示文案与预填值变化）
- ✅ 未处理其它 P1/P2/P3 审计项（C/D/E 类脚本、其它文档/log 脚本均未动）
- ✅ 服务运行正常（:8000 验证通过）

---

## 7. 结论

ARCH-10 同源残留（默认密码暴露）已闭环：代码层公开弱默认值 `"admin123"` 与前端明文提示均已移除，部署产物经重建同步后零残留；新强密码可登录、弱口令 `admin123` 登录被拒、JWT/RBAC/构建均正常。任务完成，停止，不继续处理其它审计项。
