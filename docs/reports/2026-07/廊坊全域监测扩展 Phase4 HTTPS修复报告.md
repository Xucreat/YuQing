# 廊坊全域监测扩展 Phase4 HTTPS 修复报告

- **执行时间**：2026-07-25 12:25（批准时刻）起
- **执行人**：WorkBuddy（受控执行，仅限 `data_sources` 表两行）
- **授权范围**：仅修改 `bazhou_gov`、`wenan_gov` 两个数据源的 `config_json.list_urls`，`http://` → `https://`；不改代码、不改 collector、不改其他数据源。

---

## 一、执行摘要（关键结论）

1. **目标 URL 在批准前已为 `https://`**：两数据源的 `config_json.list_urls` 最后更新时间为 **2026-07-25 12:23**（早于批准时刻约 2 分钟），当前值已均为 `https://`。因此本次 **未执行任何 DB 写入**（无可改写的 `http://`）。
2. **单源采集验证结果：两源均 `fetched=0 / created=0`**，但根因不同，且**均不在本任务授权范围内**：
   - **bazhou_gov**：`https://` 直连即失败，报 `SSLEOFError`（Python/OpenSSL 与 `www.bazhou.gov.cn` 服务端 TLS 不兼容）。**URL 协议切换无法解决**。
   - **wenan_gov**：`https://` 传输本身成功（实测可取到 71KB 真实页面），但当前配置的**根域名是 frameset 门户壳页**，无可提取文章链接 → 0 条。**需改为真实栏目页 URL + link_rule，属另一类配置变更**。
3. **区域绑定机制本身正确**：两源均正确解析到目标区域（霸州 131081→id23、文安 131026→id22），**无 131000 回退、无跨区污染**。失败纯粹发生在抓取层，与区域逻辑无关。

> 结论：授权的「HTTPS 修复」对解决两源「采集不到数据」的目标**无效且已无需执行**（目标态早已满足）；真正阻断采集的是两个独立、且超出本任务范围的底层问题，需另行批准修复。

---

## 二、执行前校验

### 2.1 目标数据库身份确认 —— ✅ VERIFIED

通过 `scripts/db_identity_check.py`（退出码 0）：

| 信号 | 实测值 | 期望值 | 结果 |
|---|---|---|---|
| system_identifier | `7663057120701798896` | `7663057120701798896` | ✅ |
| database | `opinion_db` | `opinion_db` | ✅ |
| alembic version | `p12_rbac_roleperms` | `p12_rbac_roleperms` | ✅ |
| opinions 行数 | `143` | ≥ 100 | ✅ |

连接串：`postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db`

### 2.2 修改前 config_json 快照 —— 已保存

快照文件：`_https_fix_config_snapshot_before_2026-07-25_1225.json`

| 数据源 | id | scope | updated_at | list_urls（修改前，即当前值） | 协议 |
|---|---|---|---|---|---|
| bazhou_gov（霸州市政府网） | 32 | 131081 | 2026-07-25 12:23:12 | `["https://www.bazhou.gov.cn"]` | **https** |
| wenan_gov（文安县政府网） | 35 | 131026 | 2026-07-25 12:23:36 | `["https://www.wenan.gov.cn"]` | **https** |

### 2.3 范围约束遵守

- ❌ 未修改任何代码（`service.py` / `base_http.py` / `common.py` 等均未触碰）
- ❌ 未修改任何 collector 类
- ❌ 未修改其他数据源（其余 21 个 `data_sources` 行未改动）
- ❌ 未修改 `regions` / `keywords` / 其他表

---

## 三、修改内容

- **修改字段**：`data_sources.config_json.list_urls`
- **修改前后 URL**：

| 数据源 | 修改前 | 修改后 | 实际是否改写 |
|---|---|---|---|
| bazhou_gov | `https://www.bazhou.gov.cn` | `https://www.bazhou.gov.cn` | **否（已为 https，无可改写）** |
| wenan_gov | `https://www.wenan.gov.cn` | `https://www.wenan.gov.cn` | **否（已为 https，无可改写）** |

**说明**：由于目标态（`https://`）在批准前已由外部写入（updated_at 12:23，早于批准），本次未产生任何数据库写操作。未做任何"将 http 强行改写为 https"的虚构改动。

---

## 四、执行后验证（单源采集测试）

测试方法：复刻生产装配逻辑（`resolve_collectors_verbose` → 注入单采集器 → `CollectorService.collect_and_analyze`，`trigger_type="https_fix_verify"`），独立进程运行，避免与生产 uvicorn 全局节流互相干扰。验证脚本：`_verify_https_fix.py`；原始结果：`_https_fix_verify_result.json`。

### 4.1 bazhou_gov（霸州市政府网）

| 指标 | 结果 |
|---|---|
| 解析区域 | 131081 → region_id=23 ✅ |
| fetched（抓取原始条数） | **0** |
| created（入库条数） | **0** |
| analyzed / failed | 0 / 0 |
| 回退 131000 | 否 |
| 其他区域污染 | 否 |

**根因（抓取层）**：`https://www.bazhou.gov.cn` 在 Python `requests`/urllib3（OpenSSL）下握手即失败：
```
SSLError: HTTPSConnectionPool(host='www.bazhou.gov.cn', port=443):
  Caused by SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol')
```
- `curl`（走本机代理隧道、使用 Windows SChannel）可返回 HTTP 200；但 `requests` 经同一代理仍 SSLEOFError。
- 差异在于 **TLS 协议栈**：服务端 `www.bazhou.gov.cn:443` 与 OpenSSL 协商失败，与 URL 是 `http` 还是 `https` **无关**。
- 该环境 `HTTPS_PROXY=http://127.0.0.1:7897`，生产 uvicorn 同机同代理、同 OpenSSL，**生产环境同样会失败**——属真实生产问题，非测试环境假象。

### 4.2 wenan_gov（文安县政府网）

| 指标 | 结果 |
|---|---|
| 解析区域 | 131026 → region_id=22 ✅ |
| fetched（抓取原始条数） | **0** |
| created（入库条数） | **0** |
| analyzed / failed | 0 / 0 |
| 回退 131000 | 否 |
| 其他区域污染 | 否 |

**根因（抓取层，与协议无关）**：
- `https://www.wenan.gov.cn`（根域名）返回 **750 字符** 的 `<frameset>` 门户壳页，含 `<frame src=/GOV1/Index.html>`，**0 个 `<a>` 文章链接** → 列表提取 0 条。
- 实测真实内容在 `https://www.wenan.gov.cn/GOV1/Index.html`（71,767 字符、236 个链接，栏目如 `/GOV1/Category_111/Index.aspx` 等）。
- 即：**传输层 `https` 已通，但配置的 list_url 指向了"门户壳"而非"内容列表"**，故 0 条。此问题需将 `list_urls` 指向真实栏目页并补 `link_rule` + `content_selectors`，**属不同于"协议切换"的配置变更**。

### 4.3 区域绑定正确性（独立验证点）

两源在 `_resolve_region_id` 中均按 `scope_region_codes` 最具体 code 绑定：
- bazhou → `131081`（霸州市，region_id=23）
- wenan → `131026`（文安县，region_id=22）

因两源 `created=0`，不存在"误回退 131000"或"跨区污染"的可能，验证项均为**否/无**。区域绑定逻辑本身经此前 yongqing/dacheng 验证已确认正确。

---

## 五、未修改范围

- 未修改任何源码（`app/collectors/*`、`app/services/*`、`app/routers/*` 等均未变）
- 未修改任何 collector 实现类
- 未修改 `bazhou_gov` / `wenan_gov` 之外的任何数据源
- 未修改 `regions`、`keywords`、`data_sources` 其他列（scope、enabled 等保持不变）
- 未重启 uvicorn（无代码变更，且本验证为独立进程单源跑，不影响运行实例）

---

## 六、结论与下一步建议

### 结论
授权的「HTTPS 修复」**对让两源产出数据这一目标无效**，且因目标态早已满足（12:23 已为 https），本次**未执行任何数据库写操作**。单源采集验证证明：**bazhou_gov 与 wenan_gov 当前均无法采集到任何舆情（fetched=0/created=0）**，但各自卡在完全不同的、超出本任务授权范围的根因上。

### 根因与所需修复（均超出本次授权，需另行批准）

| 数据源 | 卡点层级 | 所需修复 | 是否本次授权内 |
|---|---|---|---|
| bazhou_gov | TLS 协议栈（OpenSSL ↔ 服务端不兼容） | 代码层：为 `requests` 配置兼容的 TLS 处理（自定义 SSLContext / 代理策略 / 等价 SChannel 方案），或评估域名可达性 | ❌ 代码/collector，禁止 |
| wenan_gov | 配置层（list_url 指向 frameset 壳页） | 配置层：将 `list_urls` 改为 `https://www.wenan.gov.cn/GOV1/Index.html`（或具体栏目如 `Category_*`），并补 `link_rule`（`href_contains="Category"` 等）+ `content_selectors` | ❌ 非"协议切换"，属不同配置变更 |

### 建议的后续动作（待批准）
1. **bazhou_gov**：新建独立任务，定位其 TLS 不兼容原因并做代码层兼容（注意：会触及 `base_http.py`/`common.py` 或新增采集器参数，需走代码修改审批）。
2. **wenan_gov**：新建独立任务，做"文安县政府网栏目页发现 + link_rule 配置"，将 `list_urls` 指向 `/GOV1/Index.html` 并补链接/正文提取规则（纯配置变更，不触代码）。
3. 两任务修复后，复用本报告验证脚本 `_verify_https_fix.py` 复测，确认 `fetched>0 / created>0` 且 `region_code` 分别为 `131081` / `131026`、无 131000 回退、无跨区污染。

---

## 附：产物文件
- 修改前快照：`_https_fix_config_snapshot_before_2026-07-25_1225.json`
- 验证原始结果：`_https_fix_verify_result.json`
- 可复用验证脚本：`_verify_https_fix.py`（独立进程单源采集，参数 `bazhou_gov` / `wenan_gov`）
