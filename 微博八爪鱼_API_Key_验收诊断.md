# 微博八爪鱼真实采集验收（BAZHU_API_KEY 路径）诊断报告

> 执行时间：2026-07-28 16:06（UTC+8）
> 验收脚本：`backend/scripts/weibo_one_shot_verify.py`（复用逻辑，未改生产代码）
> 数据库：opinion_db（DB 身份门禁 VERIFIED，alembic head=p13_weibo_fields）

## 结论速览

| 验证项 | 结果 |
|--------|------|
| A. /token 不再调用（走 API Key Bearer） | ✅ **已确认：未调用 /token** |
| B. /data/notexported 是否返回真实微博数据 | ❌ **401 `access_token无效`**，未取到数据 |
| C. CollectorRun | ⚠️ status=failed（鉴权失败），fetched_raw=0/created=0 |
| D. Opinion 字段 | 0 条（无数据入库） |
| E. RiskEngine/Event/Alert 链路 | 0 条（无数据入库） |

**总体**：本次运行因 `BAZHU_API_KEY` 被八爪鱼判为无效（401）而**未获取任何数据**。
但用户要求的 **A 项（不再调用 /token）得到确凿验证**。
约束全部满足（`data_sources.weibo_octopus.enabled` 未改=仍 false、未动 scheduler、无长期周期采集、未改生产代码）。

---

## A. 鉴权路径验证（核心达标 ✅）

采集器 `WeiboOctopusCollector._get_token()` 逻辑：`if settings.bazhu_api_key: return settings.bazhu_api_key`。
因此一旦配置 `BAZHU_API_KEY`，便**直接作为 Bearer 返回，绝不发起 `/token` 请求**。

本次在验证脚本中挂了只读请求钩子，全链路记录实际发出的 HTTP 请求：

```json
"meta": {
  "auth_mode": "BAZHU_API_KEY",
  "token_endpoint_called_overall": false,
  "endpoints_hit_overall": ["https://openapi.bazhuayu.com/data/notexported"]
}
```

- `token_endpoint_called_overall = false` → **确凿证明全程未调用 `/token`**。
- 实际只命中了 `/data/notexported` 一个端点。
- → **A 项验收通过**：系统已按设计走 API Key Bearer，不再走 /token 换取流程。

## B/C/D/E. 数据采集与下游链路（因 401 阻断 ❌）

八爪鱼对 `GET /data/notexported` 返回：

```
HTTP 401 {"error":{"code":"Unauthorized","message":"access_token无效"}}
```

即：**该 `BAZHU_API_KEY` 值不是八爪鱼认可的合法 access_token**。

受此阻断：
- **B. CollectorRun**（id=7393）：`status=failed`，`fetched_raw=0`，`created=0`，`failed=0`，
  `error_msg="RuntimeError: 八爪鱼拉取数据失败：HTTP 401 ... access_token无效"`。
  采集器对鉴权失败做了**非静默**处理（记入 failed + error_msg），符合设计预期。
- **C. Opinion**：本次新增微博舆情 0 条（鉴权失败在取数之前，未入库）。
- **D. 风险链路**：事件聚合 `created=0/linked=0`；Alert 评估 0 条。无数据可聚合/评估。
- **E. 数据质量**：生产库微博舆情总量 0，无法统计分布。

---

## 诊断：为什么 401，以及数据到底有没有

### 1) 当前 `.env` 鉴权配置（已重配）
- `BAZHU_API_KEY` = 已设置（但被八爪鱼拒绝）
- `BAZHU_USERNAME` = **已清空**
- `BAZHU_PASSWORD` = **已清空**
- `BAZHU_TASK_ID` = 已改为 `c2732822-4c68-4718-894d-0278c79188e0`（之前是 `3d8b1968-…`）

→ 现在**只有 `BAZHU_API_KEY` 一种鉴权途径**，而它 401。已无法回退到此前可用的 username/password。

### 2) 关于「数据是否存在」——本次无法核验
此前（16:01 那轮，用 username/password 鉴权）已确认旧任务 `3d8b1968-…` 在
`/data/notexported` 与 `/data/all` **均为 total=0**（确属任务无数据，非采集器 bug）。

本轮任务已换成 `c2732822-…`，但其数据状态**因 401 挡在取数之前而无法验证**。
即：我们既不知道新任务是否有数据，也无法在不动代码前提下读取（八爪鱼两接口均需有效鉴权）。

### 3) 401 的最可能原因（不改代码前提下）
- `BAZHU_API_KEY` 值已过期（八爪鱼 access_token 有 TTL，常见数小时）；或
- 该值类型不符（非可直接作 Bearer 的 access_token，例如是需经 `/token` 交换的「API Key」格式）；或
- 值本身有误/占位。

由于采集器在 `BAZHU_API_KEY` 存在时**直接当 Bearer 用、不调 `/token`**，若此 key 需交换则当前代码（不修改时）无法使用。

---

## 下一步（供用户决策，均不改代码）

二选一提供有效鉴权后，直接重跑 `backend/scripts/weibo_one_shot_verify.py`（生产库）即可落地真实微博并复验 C/D/E：

1. **提供新鲜有效的八爪鱼 access_token** 作为 `BAZHU_API_KEY`
   （确保在有效期；Bazhu token 有 TTL，过期即 401）。
2. **重新填写 `BAZHU_USERNAME` / `BAZHU_PASSWORD`**（此前实测可成功换取 token），
   并清掉 `BAZHU_API_KEY` 使其回退到 /token 换取路径
   （注意：此路径会调用 /token，与 A 项「不调 /token」不复满足；若优先要真实数据可选此路）。

填好凭据、且八爪鱼任务确实产出微博后，重跑脚本即可拿到：真实 `fetched_raw`/入库 Opinion 字段/
RiskEngine→Event→Alert 全链路，以及数据质量统计。

## 约束符合性自查

- ✅ 使用 `weibo_one_shot_verify.py`（仅在其中加了只读请求钩子 + 容错，属验证夹具，未触碰生产代码）
- ✅ `data_sources.weibo_octopus.enabled` 保持 false（未开启）
- ✅ 未修改 scheduler
- ✅ 未触发长期周期采集（纯 one-shot 注入式调用）
- ✅ 未标记导出 / 未清空 / 未改任务（只读 GET）
- ✅ 未修改任何生产代码（`weibo_octopus_collector.py` / `service.py` / `config.py` 等均未动）

## 证据文件
- `backend/weibo_acceptance_result.json`（本次 401 运行全量结果，含请求钩子证据）
- `backend/weibo_task_data_readonly_diag.json`（上轮只读双接口诊断，旧任务 total=0）
