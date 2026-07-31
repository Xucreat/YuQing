# ARCH-03 清库脚本残留风险确认报告

> 阶段：交付前审计整改 · ARCH-03 只读确认阶段
> 时间：2026-07-24 18:35
> 纪律：**全程只读**（文件清单 + 内容读取 + 引用扫描 + git 跟踪核查）。**未删除、未移动、未修改任何文件、代码或数据库。**
> 前置：ARCH-01（JWT P0）、ARCH-10（admin 密码 P1）已修复闭环。

---

## 一、审计范围与方法

对代码根目录 `C:\Users\Administrator\Desktop\YQ`（**注意：真实生产数据目录为 `C:\Users\Administrator\Desktop\舆情监测系统\pgdata`**，脚本经 `SessionLocal` 连接的正是该库）盘点全部一次性脚本：

- 匹配模式：`clear_db*.py`、`fix_*.py`、`add_debug*.py`、`create_*.py`、`*.cjs/*.js` 及其它散落脚本
- 逐一读取危险脚本内容，判定：连库 / 删表 / 写库 / 改源码 / 是否绕过身份门禁
- 交叉扫描 `backend/app`、`frontend/src` 是否 import 引用
- `git ls-files` 核查是否随交付包入库

**清点结果：根目录共 32 个 `.py` + 13 个 `.cjs/.js` = 45 个一次性脚本，全部被 git 跟踪（在交付包内）。**

---

## 二、风险分级清单

### 🔴 A 类｜高危破坏性（直连生产库 + 绕过身份门禁 + 删表/写库）

| 脚本 | 行为 | 证据 | 风险 |
|---|---|---|---|
| **clear_db.py** | 清空 5 张核心业务表 | `clear_db.py:2` `from app.db.session import SessionLocal`；L13-36 依次 `delete()` **propagation_nodes / event_opinions / alert_records / events / opinions** 并 `commit()` | 误运行=生产舆情数据**全部清空且不可回滚** |
| **clear_db2.py** | 同上（精简版，无打印） | `clear_db2.py:2` SessionLocal；L12-18 删同 5 表后 `commit()` | 同上，且无任何提示更隐蔽 |
| **create_rule.py** | 删除告警规则 + 插入 + 触发重算 | `create_rule.py:2` SessionLocal；L9-12 `db.delete(AlertRule id=4)`；L16-32 `add()`+`AlertService.evaluate()` 写库 | 误运行=篡改告警规则并重算全量告警 |

**共同致命点**：三者均 `from app.db.session import SessionLocal` 直连——`SessionLocal` 绑定 `settings.database_url`（当前=生产库）。**均未调用 `db_identity_check` / 任何身份门禁**，无 `--confirm`、无环境判定、无 dry-run。放在项目根目录，双击/误 `python clear_db.py` 即执行。这正是 D1 标记的 ARCH-03 P1 核心。

### 🟡 B 类｜直连生产库（绕过门禁，但只读 SELECT）

| 脚本 | 行为 | 证据 |
|---|---|---|
| **inspect_regions.py** | 查询 regions/opinions 分布 | `inspect_regions.py:3` SessionLocal；全 `select()` 只读，无写 |
| **test_region_detail.py** | 调用 dashboard 统计 | `test_region_detail.py:3` SessionLocal + `get_dashboard_stats()` 只读 |

风险等级低（无写操作），但仍**绕过门禁直连生产库**，属工程规范问题；交付包不应包含。

### 🟠 C 类｜源码变更脚本（一次性改 backend 源文件，不连库）

一次性开发期"打补丁"脚本，直接 `write_text()` 覆盖 backend 源码，改完即废：

- **add_debug.py / clean_debug.py**：向/从 `alert_service.py` 注入/删除 `[DEBUG]` 打印
- **fix_*.py（约 22 个）**：`fix_api_init / fix_collector / fix_eval / fix_four / fix_indent / fix_models / fix_opinion_delete / fix_p1b / fix_p1b2 / fix_p2 / fix_prop / fix_prop2 / fix_prop_api / fix_prop_schema / fix_prop_service / fix_types` 等
- **fix_*.cjs/js（约 12 个）**：`fix2~fix9.cjs / fix_app.cjs / fix_l951.js / chk.cjs / chk2.cjs`
- **switch_gov.py / switch_mock.py / restore_gov.py**：切换采集器 mock/真实源（改源码）
- **decompress_write.py / decompress_deps.cjs**：node 虚拟化解压辅助

风险：误运行可能把源码**回退到旧补丁状态**，破坏当前已修复代码；且是工程卫生噪音。

### 🟢 D 类｜代码生成脚手架（写源文件字符串，不连库、不删数据）

- **create_backend.py（18KB）**：生成 schemas/router 等源文件（内含 SessionLocal/`.delete` 仅为字符串模板，非运行时 DB 操作）
- **create_alerts_vue.py / create_propagation_vue.py**：生成前端 Vue 页面

风险低（不连库不删数据），但同样是废弃脚手架。

### ⚪ E 类｜一次性测试/检查脚本

- **test_gov.py / check_css.py**：临时功能验证

---

## 三、四问四答（对照任务要求）

**Q1 哪些属于临时开发脚本？**
→ **全部 45 个**均为开发期一次性脚本。无一属于正式运维/部署工具（对比：真正的运维脚本在 `backend/scripts/`，如 `db_identity_check.py`、`init_db.py`）。

**Q2 哪些仍被项目引用？**
→ **零引用。** 扫描 `backend/app` 与 `frontend/src` 无任何 import。唯一命中 `create_rule` 是**假阳性**——`backend/app/api/alerts.py:56` 存在同名 API 端点函数 `def create_rule(...)`，与根目录 `create_rule.py` 无关。

**Q3 哪些可以安全移出交付包？**
→ **全部 45 个均可安全移出。** 无正式代码依赖，移出不影响运行时 / 构建 / 测试。（建议移至仓库外归档目录如 `Desktop\YQ_dev_scripts_archive\`，保留追溯而非删除。）

**Q4 是否存在直接连接生产库绕过身份门禁的情况？**
→ **存在，且严重。** A 类 3 个（clear_db / clear_db2 / create_rule）+ B 类 2 个（inspect_regions / test_region_detail）**共 5 个脚本经 `SessionLocal` 直连生产库且完全不经过 `db_identity_check` 门禁**。其中 A 类 3 个为破坏性写/删操作。

---

## 四、风险等级确认

| 项 | 结论 |
|---|---|
| **ARCH-03 等级** | **维持 P1（不降级）** |
| 理由 | ①`clear_db*.py` 可一键清空生产全部舆情数据且不可回滚、无门禁、无二次确认；②残留在项目根目录随交付包分发，运维/交接人员误运行概率高；③破坏后果 = 核心业务数据全损（比 admin 密码风险更直接） |
| 是否阻断交付 | **是（P1，建议交付前必须处置）**。虽非 P0（需人为误触发，非被动可利用），但破坏面为全量业务数据，企业交付标准下不可带病交付。 |

---

## 五、推荐修复方案（待确认后执行）

**方案：整体归档移出交付包（不删除，保留追溯）**

1. 在 **YQ 仓库外**新建归档目录：`C:\Users\Administrator\Desktop\YQ_dev_scripts_archive\`
2. 将 45 个根目录一次性脚本**移动**（非删除）至该目录，按 A/B/C/D/E 分类子目录存放
3. `git rm --cached`（仅从版本库移除跟踪，不物理删除工作树）后提交，使交付包不再含这些脚本
4. 验证：`git ls-files` 根目录无一次性脚本；`backend`/`frontend` 构建与 `pytest` 不受影响（已确认零引用）

> **优先处置 A 类 3 个高危脚本**（clear_db.py / clear_db2.py / create_rule.py），可作为第一批单独移出。

**不在本次范围**（按纪律不顺手处理）：
- 根目录 62 个 `.md` 报告、17 个 `.log` 日志的清理 → 独立工程卫生项
- 为 `SessionLocal` 增加运行时生产库写保护 → 属功能增强，非本审计范围
- `backend/scripts/` 下的正式脚本不动

---

## 六、本阶段合规声明

- ✅ 全程只读：`ls` / `Read` / `grep` / `git ls-files`，未执行任何脚本
- ✅ 未删除、未移动、未修改任何文件
- ✅ 未连接数据库执行任何写操作（本报告所有 DB 相关结论基于**静态代码阅读**，未运行这些脚本）
- ✅ 未修改代码 / 配置 / 数据库

**等待确认后执行第五节清理方案。**
