# Phase MediaCrawler Platform-2-E1 — Runtime Context 修复实施报告

**Phase**: MediaCrawler Platform-2-E1
**目标**: 修复 XHS real runtime blocked 问题（`FileNotFoundError: libs/douyin.js`）
**状态**: ✅ **IMPLEMENTED**（离线验证通过，未启动真实 MediaCrawler）

---

## 1. 根因（Root Cause）

上游 MediaCrawler 使用 **checkout 相对导入 / 相对文件读取**。关键证据：

```
media_platform/douyin/help.py:37
    douyin_sign_obj = execjs.compile(open('libs/douyin.js', encoding='utf-8-sig').read())
```

`open('libs/douyin.js')` 是**相对当前工作目录（cwd）** 的打开方式。只要 subprocess 的 cwd 不是 upstream MediaCrawler checkout 根目录，该相对路径就无法解析，抛出 `FileNotFoundError: libs/douyin.js`。同理，`import config` / `import main` 等 checkout 相对导入也依赖 cwd 为 checkout 根。

**原 `MediaCrawlerRuntimeFactory.config()` 的 `checkout_root` 解析链：**

```
checkout_root = override
             or media_crawler_checkout_root   # 未配置 → ""
             or root_override
             or media_crawler_root             # 运行时目录（非 upstream checkout）
             or runtime_path
```

该链**从不从 entry 推导**。生产环境若只配置了 `MEDIA_CRAWLER_ENTRY`（指向 upstream 内 `main.py` 的绝对路径）而未配置 `media_crawler_checkout_root`，`checkout_root` 会回退到 `media_crawler_root`（runtime 目录），subprocess 的 cwd 因此指向错误目录 → `libs/douyin.js` 解析失败。

**附带的隐藏陷阱**：原代码用 `Path(getattr(settings, "media_crawler_checkout_root", "") or "")`，当设置值为空字符串时得到 `Path("")`，而 `Path("")` 是**真值**（非空对象），导致 `or` 链在空值处短路，永远到不了后续候选（如 `entry.parent`），反而 `Path("").resolve()` = 当前工作目录（仓库根）。本阶段一并修复。

---

## 2. Runtime Contract 拆分（要求 2）

`MediaCrawlerRuntimeConfig` 已具备三段式契约，本阶段确保三者职责被正确绑定：

| 字段 | 职责 | 本阶段绑定 |
|------|------|-----------|
| `checkout_root` | subprocess **cwd** | upstream MediaCrawler checkout 根（= `entry.parent`） |
| `profile_root` | browser / session state | `runtime_root/upstream_profiles/{platform}/{source}/{trigger}` → 经 `MEDIA_CRAWLER_PROFILE_NAME` 注入 |
| `output_root` | artifact（JSONL 产物） | `runtime_path` → `runs/{batch}/output/{artifact}.jsonl` |

三者彼此独立：**profile 在 checkout 之外隔离，artifact 在 output 区，subprocess 只在 checkout 内执行**。

---

## 3. 修改文件列表

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/app/core/config.py` | 新增可选设置 | 增加 `media_crawler_checkout_root: str = ""`（**未改 .env**，仅新增带默认值的代码字段，未设置时不改变任何行为） |
| `backend/app/collectors/mediacrawler_runtime.py` | 核心修复 | 重构 `config()` 的 `checkout_root` 推导；移除 `prepare_upstream_profile` 中对 `runner.command_cwd` 的赋值 |
| `backend/tests/test_media_crawler_xhs_runtime_context.py` | 新增/扩展离线测试 | 新增 2 个测试；既有 2 个测试保持 |
| `docs/Phase_MediaCrawler_Platform_2E1_Runtime_Context_Implementation_Report.md` | 新增报告 | 本报告 |

---

## 4. `checkout_root` 推导设计（要求 3）

`config()` 改为：

1. 先解析 `entry`：相对 entry 用 `provisional_checkout_root` 锚定；绝对 entry 保持原路径。
2. 再推导最终 `checkout_root`（**空字符串先归一化为 `None`，避免 `Path("")` 真值陷阱**）：

```python
checkout_root = (
    self._checkout_root_override          # 显式 override（测试用）
    or checkout_setting                   # media_crawler_checkout_root（运维可显式指定）
    or entry.parent                       # 默认：entry 所在目录 = upstream checkout 根
).resolve()
```

其中 `checkout_setting = getattr(settings, "media_crawler_checkout_root", "") or None`。

**关键不变式**：`entry`（即 `MEDIA_CRAWLER_ENTRY`）在部署中是 upstream checkout 内的 `mediacrawler_standard_entry.py`，其 `Path.cwd()` 即 checkout 根，且其内部做 `import config` / `import main`。因此 `entry.parent` 必然等于 upstream checkout 根，subprocess cwd 恒正确。

`MediaCrawlerRunner` 的 `subprocess.run(..., cwd=str(self.command_cwd or run_dir))` 保持原样；`command_cwd` 仅在 runner 构造时由 `config.checkout_root` 一次性赋值，**不再被 profile 逻辑覆盖**。

---

## 5. Profile Adapter 职责收敛（要求 4）

`MediaCrawlerProfileAdapter` 只负责：

- **创建 profile**：`resolve_upstream_profile()` / `prepare()` —— 将 application profile 复制到隔离的 native view（`browser_data/xhs_user_data_dir`），**不复制 libs/config**。
- **生命周期管理**：`prepare()` 幂等创建、`cleanup()` 仅删除生成的 native view。
- **failure retention**：`prepare()` 复制失败时清理半成品并抛错。

本阶段从 `prepare_upstream_profile` 闭包中**移除 `runner.command_cwd = config.checkout_root`**，使 adapter/prepare 不再触碰 subprocess 工作目录。subprocess cwd 完全由 runtime contract（`config.checkout_root`）拥有，与 profile 生命周期解耦。

---

## 6. 离线测试结果（要求 5）

测试文件：`backend/tests/test_media_crawler_xhs_runtime_context.py`

> 测试使用 **fake upstream checkout**（临时目录内放 `libs/relative_contract.py` + `main.py`，`main.py` 执行 `from libs.relative_contract import VALUE` 与 `open('libs/douyin.js')` 等价语义的相对 cwd 读取，并断言 `Path.cwd() == EXPECTED_CHECKOUT`），**未启动真实 MediaCrawler、未触碰 upstream checkout、未使用任何真实 Cookie/token/账号**。

| 测试 | 验证点 | 结果 |
|------|--------|------|
| `test_xhs_checkout_profile_output_contexts_are_separate` | checkout-relative import 成功；XHS profile 隔离（native profile 独立目录且 marker 保留）；`xhs/jsonl` output discovery；产物 normalizer 正确 | ✅ |
| `test_weibo_legacy_runtime_keeps_checkout_and_profile_contract` | Weibo legacy contract 不变（`checkout_root`/`profile_path`/`browser_data`/`profile_name` 保持旧语义） | ✅ |
| `test_xhs_checkout_root_auto_derived_from_entry_parent` **(新增)** | **不传 `checkout_root`，仅靠 entry 自动推导**：`config.checkout_root == entry.parent`；`runner.command_cwd == checkout_root` 且 `!= native_profile`；相对 import 成功；`xhs/jsonl` discovery 保持 | ✅ |
| `test_xhs_profile_adapter_does_not_own_subprocess_cwd` **(新增)** | adapter 仅管 profile 生命周期；`runner.command_cwd` 固定为 `config.checkout_root`；运行后 adapter/binding 正确 materialize 并可 cleanup | ✅ |

**回归套件**：
- `python -m pytest -q backend/tests/test_media_crawler_xhs_runtime_context.py` → **4 passed**
- `python -m pytest -q backend/tests/test_media_crawler*.py` → **171 passed**

**编译校验**：`python -m compileall backend/app` → 干净通过（exit 0）

---

## 7. 安全 / 禁止项确认（要求 — 禁止修改检查）

| 禁止项 | 状态 |
|--------|------|
| 修改 upstream MediaCrawler | ✅ 未触碰（`D:/code files/mediaCrawler/MediaCrawler` 只读引用） |
| 复制 libs/config 到 profile | ✅ 未复制；adapter 仅复制 browser application profile 到隔离 native view |
| 修改 models（Opinion / CollectorRun） | ✅ `backend/app/models` 无改动（`git diff` 为空） |
| 修改 migration（alembic） | ✅ `backend/alembic` 无改动 |
| 修改 Scheduler | ✅ `backend/app/core/scheduler.py` 无改动 |
| 修改 .env | ✅ 未修改 `.env`（仅 `config.py` 新增带默认值的可选代码字段） |
| 修改生产 DataSource | ✅ 未改动任何 DataSource |
| 启动真实 MediaCrawler / 真实小红书采集 / 真实 Cookie/token | ✅ 全程离线 fixture + fake entry |
| 新增 Scheduler 平台分支 | ✅ 未新增 |
| 启动 Scheduler | ✅ 未启动 |

`git diff --check` → 干净（exit 0）。本次实际改动仅 `mediacrawler_runtime.py`、`config.py` 与测试文件。

---

## 8. 当前状态

✅ **IMPLEMENTED**

- `FileNotFoundError: libs/douyin.js` 的根因（subprocess cwd 指向 profile/runtime 目录而非 upstream checkout 根）已被修复：未显式配置 `media_crawler_checkout_root` 时，`checkout_root` 自动从 `entry.parent` 推导，subprocess cwd 恒为 upstream MediaCrawler checkout 根。
- profile isolation 完整保留：browser/session state 仍隔离在 `runtime_root/upstream_profiles/{platform}/{source}/{trigger}`，与 checkout 根、`output_root` 三者互不污染。
- XHS runtime contract（`xhs` cli / search·detail·creator / `xhs/jsonl` artifact）、Weibo legacy contract 均经离线测试确认不变。
- 全部离线测试通过（4/4 本阶段测试，171/171 mediacrawler 套件），编译干净，禁止项零触碰。

> 注：本阶段为 runtime contract 修复，非生产启用阶段。真实运行仍需运维显式配置 `MEDIA_CRAWLER_ENTRY`（指向 upstream checkout 内入口）与 `MEDIA_CRAWLER_REAL_RUN_GATE=true`，并经 approved enablement 步骤。
