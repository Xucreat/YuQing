# ARCH-10 admin 默认密码修复报告

> 修复项：ARCH-10 — admin 用户默认弱口令 `admin123` 风险
> 修复方案：方案 A（仅更新 `users.password_hash WHERE id=1`，最小范围）
> 执行时间：2026-07-24 18:30 GMT+8
> 执行纪律：仅修复 admin 默认密码；未改用户表结构 / username / id / role / is_superuser / RBAC / JWT / 登录接口 / 其他用户 / config.py 默认值 / 前端提示 / 其他 P1-P3。
> **新密码不在本报告、终端输出、git 记录中出现；已通过 git 仓库外本地文件单独交付管理员。**

---

## 1. 修改文件 / 数据库范围

| 类别 | 范围 | 说明 |
|---|---|---|
| 代码文件 | **无** | 未修改任何 `.py` / 配置 / 前端 / 测试 |
| 数据库表结构 | **无** | 未 DDL、未加字段、未改约束 |
| 数据库数据 | **仅** `users.password_hash WHERE id=1` | 单行 UPDATE，见下 |
| git 记录 | **无** | 密码写入 `C:\Users\Administrator\Desktop\ARCH-10_admin_new_password.txt`（YQ 仓库外，不入库） |

**执行的唯一写操作 SQL：**

```sql
UPDATE users SET password_hash = <新bcrypt哈希> WHERE id = 1;
```

---

## 2. 生产库身份确认（连库前门禁）

- `db_identity_check.py` → **[DATABASE IDENTITY: VERIFIED]**（业务指纹校验，opinions ≥ 100）
- 5432 实例进程 `-D` = `C:\Users\Administrator\Desktop\舆情监测系统\pgdata` ✅（指定的真实生产库）
- 修改前置条件核验：admin `id=1`、`username='admin'`、`password_hash` 存在（bcrypt `$2b$12$`, 60 字符）、当前 `admin123` 校验 **True**（风险成立）

---

## 3. 更新 SQL 影响行数

| 项 | 结果 |
|---|---|
| **UPDATE 影响行数** | **1**（仅 id=1）|
| 密码强度 | 长度 20（≥16），含大小写字母 + 数字 + 符号，`secrets` 安全随机生成 |
| 哈希算法 | bcrypt `$2b$12$`（cost=12，**未降低**，沿用现有 `hash_password()`）|
| 旧哈希 sha256 前缀 | `c34e315d` |
| 新哈希 sha256 前缀 | `873513c3` |

---

## 4. admin 属性前后对比

| 字段 | 修改前 | 修改后 | 一致 |
|---|---|---|---|
| id | 1 | 1 | ✅ |
| username | `admin` | `admin` | ✅ |
| role | `admin` | `admin` | ✅ |
| is_superuser | True | True | ✅ |
| is_active | True | True | ✅ |
| created_at | 2026-07-16 17:41:34.800693 | 2026-07-16 17:41:34.800693 | ✅ |
| **password_hash** | sha256 `c34e315d` | sha256 `873513c3` | **已变更（唯一变化）** |

> 除 `password_hash` 外，admin 所有属性完全不变。

---

## 5. 验证闭环结果（实测，两实例 :8000 / :8011 一致）

| 验证项 | 方法 | :8000 | :8011 | 结论 |
|---|---|---|---|---|
| **A 新密码登录** | `POST /api/login`（新密码）| HTTP **200**，获 access_token，role=admin | HTTP **200**，获 token，role=admin | ✅ 登录成功 |
| **B 旧密码失效** | `POST /api/login`（admin123）| HTTP **401** | HTTP **401** | ✅ 旧口令失效 |
| **C 新 token 访问** | `GET /api/opinions`（新 token）| HTTP **200** | HTTP **200** | ✅ JWT 访问正常 |
| **D RBAC 保持** | login 返回 permissions | `['*']`（role=admin, superuser）| `['*']` | ✅ 权限不变 |
| **E 其他用户不受影响** | id=3/id=4 password_hash md5 前后对比 | 未变 | 未变 | ✅ 未波及 |

**补充复核**：旧默认密钥伪造 token → `GET /api/opinions` 仍 **HTTP 401**（ARCH-01 门禁持续生效，本次修复未削弱）。

**库内直接校验**：新密码 `verify_password` → **True**；旧 `admin123` → **False**。

---

## 6. 结论

- ARCH-10 admin 默认弱口令风险 **已消除**：admin 现使用 20 位强随机密码（bcrypt cost 12 存储）。
- 修改范围严格限定 **单行** `users.password_hash WHERE id=1`，影响 1 行；admin 其余属性、其他用户、表结构、RBAC、JWT、登录接口、config 默认值、前端提示均未触碰。
- 五项验证（A/B/C/D/E）在两个运行实例上全部通过，修复闭环。
- **ARCH-10 由 P1 → 已修复。**

## 7. 交付与后续提醒

- **新密码交付**：写入 `C:\Users\Administrator\Desktop\ARCH-10_admin_new_password.txt`（YQ 仓库外，未入 git）。**请管理员登录改记后立即删除该文件。**
- 本次严格限定 ARCH-10 主体（库内密码）。以下同源风险按纪律**未处理**，留待后续独立阶段：
  - `config.py:46` `init_admin_password` 默认值仍为 `admin123`（仅影响未来首次初始化，对已存在 admin 无效）；
  - 前端登录页 `Login-*.js` 硬编码回显 `admin123` 提示文案。
  - 建议后续提供「用户自助修改密码」入口（当前无改密接口，密码只能经运维直接改库）。
