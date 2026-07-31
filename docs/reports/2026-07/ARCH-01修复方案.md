# ARCH-01 修复方案（P0：JWT SECRET_KEY 默认弱值导致认证绕过）

> 阶段：独立 P0 修复（只读审计约束已结束，仅针对 ARCH-01 做最小范围修复）
> 范围铁律：只处理 ARCH-01；不碰数据库结构 / 业务逻辑 / RBAC / 测试断言 / 其他 P1-P3 问题。

---

## 一、根因分析

### 证据链（均已实测/查证）
1. `backend/app/core/config.py:40` 定义 `secret_key: str = "change-me-in-production"`（源码公开默认值，长度 23）。
2. `backend/app/core/config.py:17-22` 的 `Settings` 配置 `env_file=[".env", str(_PROJECT_ROOT / ".env")]`，启动时读取项目根目录 `YQ/.env`。
3. 核对 `YQ/.env` 第 2 行：`SECRET_KEY=change-me-in-production` —— **`.env` 中配置的正是该公开弱值**（长度 23，== 默认）。
4. 运行实例（`YQ/.env` 内容被加载）连的是真实生产库（D1 已通过 `db_identity_check` 与 `db_identity.py` 双重确认指向 `舆情监测系统/pgdata`），证明 `.env` 确被 pydantic-settings 读取；而其中 `SECRET_KEY` 为弱默认 → 运行时 `settings.secret_key == "change-me-in-production"`，并进一步被 `docker-compose.yml:34-35`（`env_file: .env`）的容器化部署同样继承。
5. D1 实测：用该公开默认密钥伪造 `sub=1` 的 admin token，调用生产接口 `GET /api/opinions` 返回 **HTTP 200 + 真实数据** → 认证完全可绕过。

### 结论
根因 = **`.env` 把 `SECRET_KEY` 设成了源码公开的默认弱值**，而非"未加载 .env"。任何能读到源码/仓库的人，都能用该值签名任意身份（含 admin）的 JWT，使认证与 RBAC 全部失效。

---

## 二、修改文件与修改内容（仅 2 处，最小范围）

### 文件 1：`C:\Users\Administrator\Desktop\YQ\.env`（生产环境变量）
- **第 2 行**：`SECRET_KEY=change-me-in-production` → 替换为强随机密钥。
- 生成方式（执行时现场生成，绝不手写固定值）：
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`（取 64 字符 URL-safe 随机串）。
- 其他所有键（DATABASE_URL / INIT_ADMIN_PASSWORD / COLLECTOR_* / DEEPSEEK_* 等）**一律不动**。

### 文件 2：`C:\Users\Administrator\Desktop\YQ\backend\app\core\config.py`（生产安全门禁）
- 在 `Settings` 类增加 `secret_key` 字段校验器（`field_validator("secret_key", mode="after")`）：
  - 若 `secret_key == "change-me-in-production"` → 抛出 `ValueError`，并给出明确中文报错（提示去 `.env` 设置强随机密钥后再启动）。
  - 效果：任何以公开默认弱密钥启动生产的尝试，会在 `Settings()` 构造（即 `app` 导入）阶段直接失败，uvicorn 起不来 —— **彻底杜绝"继续使用默认密钥"**。
- 不改动 `algorithm` / `access_token_expire_minutes` / 其他字段；不触碰 RBAC、业务逻辑、数据库结构、任何测试。
- 关于测试：本机 `YQ/.env` 修复后持有强密钥，pytest 经 conftest 加载同一 `.env`，门禁不会触发；**现有测试无需修改、断言不变**。

---

## 三、修复后必须重启的服务（让新密钥与门禁生效）

仅改 `.env` + `config.py` 不会让正在运行的 uvicorn 生效，必须重启使其重新加载。

- 当前运行实例（实测）：
  - `:8000` → PID 25548（父）/ 27020（子）
  - `:8011` → PID 10236（父）/ 75212（子）
- 重启步骤（执行时）：
  1. `taskkill /F /PID 25548`、`taskkill /F /PID 27020`、`taskkill /F /PID 10236`、`taskkill /F /PID 75212` 逐个强杀。
  2. 以 `cwd=backend` 用 `backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port <port> --log-level info` 后台拉起 :8000 与 :8011。
- 说明：重启会使全部在线会话的旧 JWT 失效（见第四节），属预期安全结果。

---

## 四、Token 影响评估

- JWT 为无状态签名令牌，密钥即信任根。更换 `SECRET_KEY` 后：
  - **此前签发的全部 token（含任何已被利用的伪造 token）签名校验失败 → 401，立即失效**。这正是修复期望的副作用，可清除潜在被伪造会话。
  - 已登录用户（前端持有旧 token）下一次受保护请求会收到 401；按现有无状态设计（无 refresh token），用户**重新登录**即可获得新 token，无需任何代码改动。
  - **不建议**做"旧 token 白名单 / 过渡期"——会重新引入风险。直接强制重登。
- 登录接口逻辑不变（`auth.py` 仍用 `create_access_token` 按 `settings.secret_key` 签名）；重新登录即可正常签发新 token。

---

## 五、风险评估

| 风险 | 等级 | 说明与缓解 |
|------|------|-----------|
| 重启造成短暂中断 + 全部用户需重新登录 | 中 | 安全修复必然代价；建议在低谷期执行，运营侧通知重登。 |
| `.env` 写入后格式/编码异常导致解析失败 | 低 | Edit 仅改单值行、保留其余行；重启前用只读脚本预校验 `settings.secret_key` 已变为强值且门禁通过。 |
| 门禁误杀合法启动 | 低 | 仅当 == 公开默认弱值才拒绝；强密钥（含测试库场景）一律放行；不依赖任何新增环境变量。 |

**不在本方案范围（按指令明确排除）**：`INIT_ADMIN_PASSWORD=admin123`（P1）、CORS 全开（P1）、`/_debug_static` 调试端点（P2）、`clear_db*.py` 残留（P1）、索引缺失（P2）等——均不处理、不优化。

---

## 六、回滚方式

- **代码回滚**：若 `config.py` 门禁导致非预期拒绝，`git checkout backend/app/core/config.py` 还原（保留 `.env` 强密钥，漏洞仍修复）。
- **密钥回滚**：极端情况下如需回退到弱密钥（**不推荐**），将 `.env` L2 还原为原值即可；强烈建议保留强密钥。
- **服务回滚**：重启失败时，`taskkill` 后重新拉起原命令（启动命令未变）。

---

## 七、验证清单（执行后写入《ARCH-01 P0 修复报告》）

1. **SECRET_KEY 运行时验证**：重启后独立进程加载 `settings`，确认 `secret_key != "change-me-in-production"` 且长度 ≥ 48。
2. **默认密钥伪造 token 验证失败**：用公开默认密钥伪造 admin token 调 `GET /api/opinions` → 期望 **HTTP 401**（D1 时为 200）。
3. **原有登录流程验证**：`POST /api/login`（admin/admin123）→ 200 返回 `access_token`；用该 token 调受保护接口 → 200。
4. **回归测试**：在 `backend` 以 `DATABASE_URL=postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test DB_IDENTITY_CHECK=off` 运行 `pytest`（**不修改任何测试文件/断言**），记录通过/失败。
