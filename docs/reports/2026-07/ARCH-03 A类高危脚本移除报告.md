# ARCH-03 A 类高危脚本移除报告（第一阶段）

> 交付前全面审计 · 整改阶段 · ARCH-03 第一阶段
> 执行时间：2026-07-24 22:36
> 执行原则：仅处理 ARCH-03 A 类 3 个高危脚本；移动归档、不删除、不改内容；不触碰其他 P1/P2/P3。

---

## 1. 执行范围

| 项 | 内容 |
|---|---|
| 处理对象 | `clear_db.py`、`clear_db2.py`、`create_rule.py`（A 类高危，共 3 个） |
| 归档目标 | `C:\Users\Administrator\Desktop\YQ_dev_scripts_archive\A_high_risk\` |
| 操作方式 | `git rm --cached`（移除索引）+ 物理 `mv`（移动，非删除） |
| 脚本内容 | **未修改**（字节数与原始一致：1310 / 782 / 1249） |
| 其他脚本 | B/C/D/E 类**未处理**（留第二阶段） |
| 数据库 | **未做任何写操作** |

---

## 2. 修改文件 / 范围

**Git 索引变更（仅移除跟踪，不删除本地文件）：**

```
D  clear_db.py        (git rm --cached，工作树文件已移走)
D  clear_db2.py       (git rm --cached，工作树文件已移走)
D  create_rule.py     (git rm --cached，工作树文件已移走)
```

**物理位置变更（移动归档）：**

| 脚本 | 原位置 | 现位置 | 字节数 |
|---|---|---|---|
| clear_db.py | `YQ\clear_db.py` | `YQ_dev_scripts_archive\A_high_risk\clear_db.py` | 1310 |
| clear_db2.py | `YQ\clear_db2.py` | `YQ_dev_scripts_archive\A_high_risk\clear_db2.py` | 782 |
| create_rule.py | `YQ\create_rule.py` | `YQ_dev_scripts_archive\A_high_risk\create_rule.py` | 1249 |

> 说明：`git rm --cached` 在先、`mv` 在后。全程未读取脚本内容（规避 node 虚拟化压缩字节问题），字节数比对证明内容零改动。归档为**移动**，本地文件完整保留在仓库外，可随时恢复。

---

## 3. 验证闭环（4 项全部通过）

### ① git ls-files 不再包含三文件 ✅
```
$ git ls-files clear_db.py clear_db2.py create_rule.py
（空 —— 已从 git 跟踪移除）
$ git status --short（三文件）
D  clear_db.py
D  clear_db2.py
D  create_rule.py
```
仓库根目录已无这三个 `.py` 文件（`ls` 报 No such file）。

### ② backend/app、frontend/src 无引用 ✅
```
$ grep -rnE "\b(clear_db|clear_db2|create_rule)\b" backend/app frontend/src
（无任何 import / 调用引用）
```
> `create_rule` 在 `alerts.py:56` 的命中为同名 API 端点函数 `def create_rule(...)`，属假阳性，与根目录脚本无关。移除三脚本不影响任何正式代码。

### ③ 服务启动正常 ✅
```
清理前： :8000 → PID 72396,  :8011 → PID 31672  (LISTENING)
清理后： :8000 → PID 72396,  :8011 → PID 31672  (LISTENING)
```
两实例**同 PID 持续监听、未重启、未中断**——移除脚本对运行时零影响。

### ④ 数据库无任何写入变化 ✅

连库前经 `db_identity_check.py` → **VERIFIED**（真实生产库 `舆情监测系统\pgdata`）。逐表行数快照对比：

| 表 | 清理前 | 清理后 | 一致 |
|---|---|---|---|
| opinions | 1085 | 1085 | ✅ |
| events | 212 | 212 | ✅ |
| event_opinions | 441 | 441 | ✅ |
| alert_records | 80 | 80 | ✅ |
| propagation_nodes | 662 | 662 | ✅ |
| alert_rules | 2 | 2 | ✅ |

**数据库零写入确认：全表行数不变，无 DELETE / INSERT / UPDATE。**

---

## 4. 结论

- ARCH-03 **第一阶段（A 类 3 个高危脚本）处置完成**：三个可一键清空生产数据、绕过身份门禁、不可回滚的破坏性脚本已移出 git 跟踪、移出交付包目录，物理归档保留于仓库外。
- 4 项验证全部通过：git 不再跟踪、无代码引用、服务未中断、数据库零写入。
- 交付包中不再包含这三个高危清库脚本，**误运行清空生产数据的风险已消除**。

## 5. 待处理（第二阶段，待本阶段验证通过后授权）

| 类别 | 脚本 | 风险 |
|---|---|---|
| 🟡 B 类 | inspect_regions.py、test_region_detail.py | 只读但直连生产库绕门禁 |
| 🟠 C 类 | add_debug/clean_debug、fix_*.py(~22)、fix_*.cjs(12)、switch_gov/switch_mock/restore_gov 等 | 一次性改源码脚本 |
| 🟢 D 类 | create_backend.py、create_alerts_vue.py、create_propagation_vue.py | 源码脚手架 |
| ⚪ E 类 | test_gov.py、check_css.py、chk*.cjs | 临时验证脚本 |

> 建议按同样"移动归档、不删除、git rm --cached"方式处理，B 类优先（仍绕门禁连生产库）。等待您确认第一阶段后再执行。
