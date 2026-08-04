# Phase DataSource-National-Mode-2 实施报告

> 阶段目标：在 **不修改 Opinion/Event/Risk 模型、不放开 `region_id=NULL`** 的前提下，
> 为未来 `national` collection_mode 提供合法 `region_id` 承载。
> 采用方案：插入一条系统级「全国」哨兵 Region 数据行 + 后端常量/只读解析能力。
> 本阶段仅做数据准备，**未配置 national 采集、未放行准入、未产生任何全国数据入库**。

---

## 1. 实施前审计结果

详见同目录 `Phase_DataSource-National-Mode-2_PreAudit.md`。核心结论：

- `regions` 表字段：`id`(PK)、`code`(UNIQUE)、`name`、`level`、`parent_code`；**无软删除字段、无 `enabled`/`national` 列**。
- 当前 `code='000000'` / `name='全国'` **不存在**（直查 NONE）。
- 外键：`opinions.region_id` 与 `events.region_id` 均引用 `regions.id`；新增行 = 新增合法 FK 目标，**零外键风险**。
- 聚合：`dashboard._rollup_provinces` 仅遍历「有 Opinion 的 region_id」；哨兵 id 当前不在该序列 → 不进入省级输出。`_province_code("000000")` → `"000000"`，与真实省 key `"130000"` **不冲突**。
- 前端：当前仅消费有数据的 region；无数据指向哨兵 → 地图/卡片无变化。
- 审计结论：**可安全新增一条哨兵 Region 行**，对 FK/聚合/前端零异常风险。

---

## 2. 为什么选择哨兵 Region（而非其他方案）

约束红线：**禁止放开 `Opinion.region_id` nullable、禁止新增字段/列、禁止改模型**。

| 候选方案 | 是否满足约束 | 评价 |
|----------|--------------|------|
| **A. 哨兵 Region 行（采用）** | ✅ | 复用现有 `regions` 表 + 固定 `code='000000'`；零 schema 变更；同时满足 FK 与 NOT NULL；不污染现有区域统计；dashboard 上卷 key 独立。 |
| B. 放开 `region_id=NULL` | ❌ 红线禁止 | 直接违反约束；且 Event/Risk 聚合以 `region_id` 为合并/统计键，NULL 会破坏聚合链路。 |
| C. 新增 `national`/`is_national` 列 | ❌ 红线禁止 | 新增字段/迁移，违反「不新增字段」。 |
| D. 复用某现有 Region（如河北省 130000） | ❌ 语义错误 | 全国稿会被错误归属河北，污染廊坊/河北区域监测统计。 |

→ **哨兵 Region 是唯一同时满足「不新增字段 + 不放开 NULL + 不污染现有区域 + 不改模型」的方案。**
全国身份完全由固定 `code='000000'` 表达；`level='province'`（全国=行政区划树最顶层，类比省级 `parent_code` 为空），**不新增 `national`/`is_national` 列**。

---

## 3. 修改文件列表

| 文件 | 类型 | 变更 |
|------|------|------|
| `backend/app/constants/__init__.py` | 新增 | 空包标记，使 `app.constants` 成为可导入包。 |
| `backend/app/constants/region.py` | 新增 | 定义 `NATIONAL_REGION_CODE = "000000"`（唯一常量，零依赖、可被任意模块安全导入，供 National-4 复用）。 |
| `backend/app/services/opinion_region_service.py` | 修改 | ① 顶部新增 `from app.constants.region import NATIONAL_REGION_CODE`；② 新增模块级函数 `resolve_national_region(db)`——**只读查询**哨兵 Region，**绝不自动创建**，缺失时抛 `RuntimeError`（快速失败）。 |
| `docs/Phase_DataSource-National-Mode-2_PreAudit.md` | 新增 | 只读审计文档。 |
| `backend/_verify_national_mode2.py` | 新增 | 只读验证脚本（不写库）。 |
| `docs/Phase_DataSource-National-Mode-2_实施报告.md` | 新增 | 本文件。 |

> 未触碰：`Opinion`/`Event`/`Risk` 模型、`scheduler`、`registry`、`collector`、`frontend`、任何 `migration`、任何数据库表结构。

---

## 4. 数据库变化

**仅新增 1 条 `regions` 数据行**（唯一允许的写操作）：

| 列 | 值 |
|----|----|
| code | `000000` |
| name | `全国` |
| level | `province` |
| parent_code | `NULL` |
| id | `24`（自增） |

计数变化：

| 表 | 变更前 | 变更后 |
|----|--------|--------|
| regions | 23 | **24**（+1，仅此） |
| opinions | 1023 | 1023（不变） |
| events | 175 | 175（不变） |
| alert_records | 11 | 11（不变） |

**未产生任何全国数据入库**：无任何 `opinion` 的 `region_id` 指向 `24`。

---

## 5. 回滚方式

本阶段变更**完全可回滚**，分两步（顺序无关）：

```sql
-- 1) 删除哨兵 Region 行（单条，可回滚）
DELETE FROM regions WHERE code = '000000';
```

```bash
# 2) 回退代码（撤销 3 个文件的新增/修改）
#    - 删除 backend/app/constants/region.py
#    - 删除 backend/app/constants/__init__.py
#    - 在 backend/app/services/opinion_region_service.py 中
#      移除顶部 `from app.constants.region import NATIONAL_REGION_CODE` 导入
#      与 `resolve_national_region(db)` 函数定义
```

回滚后系统状态与 Phase 2 实施前完全一致（regions=23，无 `app.constants` 包，无 `resolve_national_region`）。

---

## 6. 验证结果

运行 `backend/.venv/Scripts/python.exe _verify_national_mode2.py`（只读），**10/10 全部 PASS**：

| 项 | 结果 |
|----|------|
| A. 全国 Region 存在 (code=000000) | ✅ count=1 |
| B. 全国记录唯一 (<=1) | ✅ count=1 |
| C. ORM 加载 Region 正常 | ✅ id=24 name=全国 level=province |
| C. resolve_national_region 可用 | ✅ id=24 |
| D. Opinion.region_id 可承载全国 id（内存构造，不写库） | ✅ region_id=24 |
| D. dashboard 省级聚合无异常且不含哨兵 | ✅ rolled_province_ids=[2]（仅河北省，哨兵未泄漏） |
| E. regions 数量仅 +1 (23→24) | ✅ |
| E. opinions 数量不变 | ✅ 1023 |
| E. events 数量不变 | ✅ 175 |
| E. alert_records 数量不变 | ✅ 11 |

> 说明：dashboard 当前省级上卷结果仅含 `id=2`（河北省 130000），哨兵 `id=24` 不出现——证明新增行**未影响现网聚合**。

---

## 7. 对 National-3 的接口准备说明

本阶段交付两项可复用能力，作为 National-3（配置化 API）/ National-4（准入+地域解析）的基座：

1. **`NATIONAL_REGION_CODE`（常量，单点定义）**
   - National-3 在 `data_sources.config_json` 校验白名单中识别 `collection_mode: "national"` 时，可直接引用该常量，无需硬编码字符串。
   - 可经 admin API 暴露给前端，使前端知晓「全国」哨兵 code，为 National-5 地图/筛选做准备。

2. **`resolve_national_region(db)`（只读解析入口）**
   - National-4 准入逻辑在判定「全国源 + 纯主题命中」时，调用本函数获取合法 `region_id` 兜底，写入 `Opinion.region_id`，从而**在不放开 NOT NULL 的前提下完成全国稿入库**。
   - 缺失时抛 `RuntimeError` → 调用方快速失败，避免静默写入 NULL/脏数据。

**边界声明（本阶段明确不做，留待后续 Phase）**：
- ❌ `national` collection_mode 配置（National-3）
- ❌ admission 放行 / `region_decision` 改造（National-4）
- ❌ `topic_only` 全量采集（National-4）
- ❌ 前端全国展示（National-5）
- ❌ 修改 dashboard 全国展示（National-5）

---

## 验收标准核对

| 验收项 | 状态 |
|--------|------|
| PreAudit 已生成 | ✅ |
| regions 表结构已确认 | ✅ |
| 全国 Region 不重复 | ✅ (count=1) |
| NATIONAL_REGION_CODE 常量存在 | ✅ |
| resolve_national_region 可用 | ✅ |
| 未修改 Opinion/Event/Risk | ✅ |
| 未修改 migration | ✅ |
| 未修改 scheduler/registry | ✅ |
| 未扩大采集范围 | ✅ |
| 未产生全国数据入库 | ✅ |
| 验证脚本 PASS | ✅ (10/10) |
| 实施报告完成 | ✅ |

**结论：Phase DataSource-National-Mode-2 完成，所有验收项通过。**
