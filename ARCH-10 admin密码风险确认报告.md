# ARCH-10 admin 默认密码风险确认报告

> 阶段：交付前全面审计 · 整改阶段（ARCH-10 只读确认）
> 时间：2026-07-24 18:25
> 纪律：**全程只读**（文件读取 + SELECT + bcrypt 本地校验），未修改任何代码 / 数据库 / 密码 / 配置 / 认证逻辑
> 数据库身份：**VERIFIED**（`db_identity_check.py` 退出码 0，opinions 业务指纹匹配，真实生产库 `舆情监测系统/pgdata`）

---

## 一、审计范围

仅确认 D1 发现的 **ARCH-10（admin 默认密码风险）**，不涉及其它 P1/P2/P3。检查四项：
1. 当前 users 表 admin 用户信息
2. admin 密码哈希是否存在
3. 是否能确认当前密码仍为默认 `admin123`
4. `init_admin_password` 配置的实际作用范围

---

## 二、当前 admin 用户状态（证据）

**证据来源**：只读 SQL `SELECT ... FROM users`（生产库，2026-07-24 18:25）

| id | username | role | is_superuser | is_active | 哈希算法 | 哈希长度 | created_at |
|----|----------|------|--------------|-----------|----------|----------|------------|
| 1 | `admin` | admin | **True** | True | `$2b$12$`（bcrypt, cost 12） | 60 | 2026-07-16 17:41:34 |
| 3 | `测试` | analyst | False | True | `$2b$12$` | 60 | 2026-07-23 |
| 4 | `观察测试` | viewer | False | True | `$2b$12$` | 60 | 2026-07-24 |

- admin 为 **id=1、role=admin、is_superuser=True、is_active=True** 的最高权限账户。
- **密码哈希存在**，且为规范 bcrypt（`$2b$12$` 前缀、60 字符、含 salt）。**密码本身未明文存储，存储层安全。**

---

## 三、默认密码风险确认（核心结论）

**方法**：读取 admin 的 `password_hash`，在本地用 `bcrypt.checkpw` 逐一校验候选口令（纯只读，不发登录请求、不改数据）。

| 候选口令 | 校验结果 |
|----------|----------|
| **`admin123`** | ✅ **匹配（True）** |
| admin / 123456 / password / admin@123 / Admin123 | 均不匹配 |

> **风险确认成立**：admin(id=1, 超级管理员) 当前密码**仍为默认弱口令 `admin123`**，从未修改。

### 加重因素（旁证，非新增审计项）
- `backend/app/core/config.py:46` — `init_admin_password: str = "admin123"`（源码公开默认值）。
- `backend/app/static/assets/Login-*.js:16 / :85` — **前端登录页硬编码回显 `admin123` 作为提示**（当前生效版本 `Login-CpWMT7Ce.js`），等于把管理员默认口令公开写在登录界面。

### 与 ARCH-01 的关联（风险升级逻辑）
ARCH-01 修复后 JWT 已无法伪造，**密码成为 admin 超级账户唯一的认证屏障**。而这唯一屏障是一个"源码公开 + 登录页明示"的默认弱口令 —— 任何能访问登录页的人都可直接以超级管理员登录。因此该问题**不应降级**。

---

## 四、`init_admin_password` 配置作用范围（澄清）

**证据**：`backend/scripts/init_db.py:417-428`

```python
admin = db.query(User).filter(User.username == settings.init_admin_username).first()
if admin is None:
    db.add(User(username=..., password_hash=hash_password(settings.init_admin_password), role="admin"))
    # 已创建管理员用户
else:
    # 管理员用户已存在，跳过
```

- `init_admin_password` **仅在 `init_db.py` 首次初始化、且 admin 不存在时**用于生成初始哈希；**幂等**：admin 已存在则完全跳过。
- 运行时认证、登录接口 (`api/auth.py`)、修改密码等流程**均不引用** `init_admin_password`（全局仅此一处使用）。
- **含义**：修改 `config.py` 里的默认值或 `.env` 里的 `INIT_ADMIN_PASSWORD` **对已存在的 admin 无效**（不会回改现有密码）。因此**消除风险必须直接更新库内 `password_hash`**，改配置无用。

---

## 五、风险等级确认

| 项 | 结论 |
|----|------|
| 风险是否真实存在 | **是**（bcrypt 校验实证 admin123 有效） |
| 影响账户 | id=1 超级管理员（最高权限） |
| 可利用性 | 极高（默认口令源码公开 + 登录页明示，无需任何前置条件） |
| 修复前置依赖 | 无（ARCH-01 已修复，JWT 已安全，仅剩密码屏障失守） |
| **等级判定** | **维持 P1（不降级）** — 建议交付前必须修复；鉴于是超级账户唯一认证屏障，实际危害接近 P0，但因需本地/网络可达登录页且非"无凭证绕过"，仍归 P1 |

---

## 六、推荐修复方案

### 方案 A（推荐，最小范围）— 直接更新 admin 的 password_hash

- 为 admin 生成新的**强随机密码**（如 `secrets.token_urlsafe`），bcrypt 哈希后 **仅 UPDATE `users.password_hash` WHERE id=1**。
- **不改**：user id、username、role、is_superuser、RBAC、JWT 逻辑、登录接口、表结构、字段。
- 新密码通过安全渠道单独交付管理员，不写入任何报告 / 日志 / 版本库。
- 验证四项：① 新密码登录成功 ② 旧密码 `admin123` 登录失败 ③ JWT 访问受保护接口正常 ④ RBAC 权限保持一致（仍为 admin/superuser）。

**回滚**：修复前先记录旧 `password_hash`（仅内存/临时，不落盘），如需回滚 UPDATE 回旧哈希即可；因是安全修复，通常无需回滚。

### 伴随建议（**本次不执行**，仅提示，属独立范围）
- `config.py:46` 默认值与前端登录页 `admin123` 提示回显应在后续独立整改中一并清除，避免"库里改了、界面仍教用户用默认口令 + 新初始化仍用弱默认"。本次严格限定 ARCH-10 主体（库内密码），不动这两处。

---

## 七、审计纪律声明

- 本报告全程只读：未修改数据库、未修改密码、未修改认证逻辑、未修改配置、未删除文件。
- 所有结论均有证据支撑（SQL 结果 / 文件行号 / bcrypt 本地校验）。
- 修复动作（方案 A）**等待确认后**再执行，并另出《ARCH-10 修复报告》。
