# ARCH-01 P0 修复报告
## JWT SECRET_KEY 默认弱值导致认证绕过 —— 最小范围修复与验证

> 修复日期：2026-07-24 ｜ 范围：仅 ARCH-01 ｜ 数据库结构 / 业务逻辑 / RBAC / 测试断言 / 其他 P1-P3 均未触碰

---

## 1. 修改文件列表

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `C:\Users\Administrator\Desktop\YQ\.env` | 配置（生产环境变量） | 第 2 行 `SECRET_KEY` 由默认弱值替换为 64 位强随机密钥（gitignored，不入库） |
| `C:\Users\Administrator\Desktop\YQ\backend\app\core\config.py` | 代码（生产安全门禁） | 新增 `secret_key` 字段校验器，默认弱值即拒绝启动 |

---

## 2. 修改前后差异

### 2.1 `.env`（第 2 行）
```
- SECRET_KEY=change-me-in-production
+ SECRET_KEY=<64 位强随机密钥，由 secrets.token_urlsafe(48) 生成，不在此输出>
```
> 密钥长度 64，sha256 前缀 `f0e09327`。完整密钥未在任何输出/版本库中暴露。

### 2.2 `backend/app/core/config.py`
新增字段校验器（位于 `Settings` 类内，紧邻 `gov_news_urls` 校验器之后）：
```python
@field_validator("secret_key")
@classmethod
def _reject_default_secret_key(cls, v: str) -> str:
    """生产安全门禁（ARCH-01 修复）：禁止以公开默认弱密钥启动。"""
    if v == "change-me-in-production":
        raise ValueError(
            "SECRET_KEY 仍为公开默认弱值 'change-me-in-production'，"
            "存在认证绕过风险（ARCH-01）。请在生产 .env 中设置强随机密钥"
            "（python -c \"import secrets; print(secrets.token_urlsafe(48))\"）后重试。"
        )
    return v
```
- 门禁**无条件**拒绝默认弱值；强密钥（含测试库场景）一律放行，不依赖任何新增环境变量。
- 未改动 `algorithm` / `access_token_expire_minutes` / 其他字段，未触碰 RBAC、业务逻辑、数据库、任何测试。

---

## 3. SECRET_KEY 运行时验证结果 ✅

重启后独立进程加载 `settings`：
- 长度：**64**（原默认弱值长度 23）
- sha256 前缀：**`f0e09327`**
- `!= "change-me-in-production"`：**True**
- `config.py` 门禁：以默认弱值构造 `Settings` → 抛 `ValidationError`；以强密钥构造 → 成功。

---

## 4. 默认密钥伪造 token 验证失败结果 ✅（核心修复点）

用源码公开默认弱值 `change-me-in-production` 伪造 `sub=1` 的 admin token，请求受保护接口：

| 实例 | 接口 `GET /api/opinions` | 结果 |
|------|--------------------------|------|
| :8000 | 旧默认密钥伪造 token | **HTTP 401** `{"detail":"Invalid token"}` |
| :8011 | 旧默认密钥伪造 token | **HTTP 401** `{"detail":"Invalid token"}` |

> 对比 D1 实测：修复前同一伪造 token 返回 **HTTP 200 + 真实数据**（认证完全可绕过）；修复后返回 **401**，认证绕过已封堵。

---

## 5. 原有登录流程验证结果 ✅

| 实例 | 步骤 | 结果 |
|------|------|------|
| :8000 | `POST /api/login`（admin/admin123） | **HTTP 200**，返回 `access_token` |
| :8000 | 用新 token 访问 `GET /api/opinions` | **HTTP 200**（返回真实舆情数据） |
| :8011 | `POST /api/login`（admin/admin123） | **HTTP 200**，返回 `access_token` |
| :8011 | 用新 token 访问 `GET /api/opinions` | **HTTP 200** |

> 登录逻辑（`auth.py` 仍用 `create_access_token` 按 `settings.secret_key` 签名）未变，重新登录即可正常签发新 token。

---

## 6. 双服务运行态确认（不输出完整密钥）

| 项 | 结果 |
|----|------|
| secret_key 长度 | **64** |
| secret_key sha256 前缀 | **`f0e09327`** |
| 两实例是否一致 | **一致 ✅**（见下） |

**一致性实证**：`:8000` 签发的 token 在 `:8011` 被接受（200），`:8011` 签发的 token 在 `:8000` 被接受（200）→ 两实例加载的是**同一 SECRET_KEY**。

> 当前运行实例：`:8000` → PID 16988，`:8011` → PID 31672（均为本次重启后新拉起，已加载新密钥与门禁；启动日志均显示 "Application startup complete"，门禁未误杀）。

---

## 7. 回归测试结果（pytest，辅助验收）

运行命令（仅切换可达测试库地址，未改动任何测试文件）：
```
DATABASE_URL=postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test DB_IDENTITY_CHECK=off pytest -q
```
结果：**190 passed, 14 failed, 11 errors, 153 warnings**（53s）。

### 失败归类（均与 ARCH-01 无关，为既有问题）
- **AI 分析**（`test_ai_analysis.py`）：`DeepSeek 调用失败 402 Insufficient Balance` —— 外部 API 额度不足，非认证问题。
- **采集 / 政府采集器**（`test_collector.py`、`test_government_collector.py`）：采集去重、服务集成、配置开关等业务断言/DB 异常。
- **事件聚合**（`test_events.py`、`test_events_aggregator_v2.py`）：事件聚合契约与分页断言。
- **关键词词库**（`test_keyword_lexicon.py`）：`total == 29` 断言（实际 30），关键词统计口径。
- **仪表盘**（`test_dashboard.py` 11 ERROR）：`sqlalchemy.exc.IntegrityError` —— 测试库数据/约束状态，与密钥无关。

**关键佐证**：`test_rbac.py` 仅 89 个 warning、**零失败/错误** —— 证明本次 `SECRET_KEY` 改动未影响认证与 RBAC 相关测试；所有失败均位于 AI/采集/事件/关键词/仪表盘等业务域，属交付前审计中已识别的独立技术债，**不在 ARCH-01 范围内，未做任何修改**。

---

## 8. Token 影响评估

- JWT 为无状态签名令牌，密钥即信任根。更换 `SECRET_KEY` 后：
  - **此前签发的全部 token（含任何被利用的伪造 token）签名校验失败 → 401，立即失效**，清除潜在被伪造会话。✅ 期望的安全结果。
  - 已登录用户（前端持有旧 token）下次受保护请求将收到 401，按现有无状态设计（无 refresh token）**重新登录**即可获新 token，无需代码改动。
  - 未做"旧 token 白名单 / 过渡期"——避免重新引入风险。
- 运营建议：修复后全员需重新登录（已在重启后日志中观察到旧 token 请求已转为 401）。

---

## 9. 风险评估与回滚

- **风险（中）**：重启造成秒级中断 + 全员重新登录。属安全修复必然代价，已在低谷期执行。
- **风险（低）**：`.env` 写入异常。已通过 Edit 单值行 + 重启前预校验（`secret_key` 变强、门禁通过）规避。
- **回滚方式**：
  - 代码：`git checkout backend/app/core/config.py`（保留 `.env` 强密钥，漏洞仍修复）。
  - 密钥：极端情况如需回退（**不推荐**），将 `.env` L2 还原即可。
  - 服务：启动命令未变，重启失败可原样拉起。

---

## 10. 结论

ARCH-01（P0 认证绕过）已**最小范围修复并验证闭环**：
1. 运行时 `secret_key` 不再为默认弱值（64 位强密钥）。
2. 旧默认密钥伪造 token 被拒（401），认证绕过封堵。
3. 真实登录流程正常，新 token 可访问受保护接口。
4. 生产安全门禁就位——未来任何以默认弱值启动生产的尝试都会在导入阶段直接失败。
5. 双实例（:8000 / :8011）加载同一密钥，运行态一致。

**ARCH-01 由 P0 降级为已修复，不再阻塞交付。** 其余 P1/P2/P3（admin 默认密码、CORS 全开、`/_debug_static`、索引缺失等）按审计纪律未处理，留待后续独立阶段。
