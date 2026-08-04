# Phase DataSource-National-Mode-2 PreAudit（只读审计）

> 阶段定位：仅做 National-Mode-1 结论落地的「数据准备」前置审计。
> 本文件为 **只读审计产出**，不修改代码、不修改数据库、不新增字段/表/migration。
> 所有写入操作（插入哨兵 Region）在审计通过后的 Step 3 才执行。

---

## A. regions 表结构确认

来源：`backend/app/models/region.py` + 生产库 `information_schema` 直查。

| 项 | 结论 |
|----|------|
| 表名 | `regions`（`Base.metadata`，`__tablename__ = "regions"`） |
| 字段 | `id` (int, PK, NOT NULL)、`code` (varchar(32), **UNIQUE+index**, NOT NULL)、`name` (varchar(128), NOT NULL)、`level` (varchar(32), NOT NULL)、`parent_code` (varchar(32), index, **nullable**) |
| 主键 | `id`（`regions_pkey`） |
| `code` 唯一 | ✅ `unique=True`（`regions_code_key`） |
| `name` 唯一 | ❌ DB 层无唯一约束；当前 23 条数据 `name` 均不重复（`COUNT(DISTINCT name)=23`） |
| 软删除字段 | ❌ 无（`deleted_at`/`is_deleted` 均不存在） |
| 层级字段 | `level`（province/city/county/street/unit）+ `parent_code`（存父级 code，非 id）；省级 `parent_code` 为空 |
| 是否存在 `code='000000'` / `name='全国'` | ❌ **不存在**（直查 NONE） |

**结论**：表结构允许安全插入一条新 Region（无唯一冲突、无软删除逻辑干扰）。

---

## B. region_id 使用范围审计（只读搜索）

涉及：`Opinion.region_id`、`Event.region_id`、dashboard 聚合、Event 聚合、Alert 聚合。

### B.1 外键关系（生产库直查）
| FK 约束名 | 引用表 | 列 |
|-----------|--------|----|
| `opinions_region_id_fkey` | opinions | region_id → regions.id |
| `fk_events_region_id_regions` | events | region_id → regions.id |

- 新增一条 regions 行 = 新增一个**合法 FK 目标**，不会触发外键异常。
- 当前无任何 Opinion/Event 指向该哨兵（插入前其 id 尚不存在）。

### B.2 聚合链路影响（代码级只读）
- **dashboard `_rollup_provinces`**：遍历的是「有 Opinion 的 `region_id` 计数序列」（`SELECT Opinion.region_id, count ... GROUP BY Opinion.region_id`）。哨兵 id 当前不在该序列中 → **不会进入省级输出**。
  - `_province_code("000000", *)` 固定返回 `"000000"`，与真实省 key `"130000"` **不冲突**，不会产生错误上卷归属。
- **dashboard `_detail_regions`**：`JOIN Opinion WHERE Region.level != 'province'`。哨兵即便 `level='province'` 也被显式排除；且当前无 Opinion 指向它 → **不进入地区 TOP 卡片**。
- **Event 聚合器**：以 `region_id` 作为合并硬门槛（`a.region_id != b.region_id` 不合并），仅作用于已存在事件成员；新增 region 行不影响现有 175 个事件。
- **Alert 聚合**：`alert_service` 按 region 仅做展示；无 Opinion/Event 指向哨兵 → 无影响。

### B.3 前端展示
当前 dashboard 仅消费「有数据的 region」。无任何 Opinion 指向哨兵 → 地图/卡片/列表 **无任何变化**。
> 理论风险（仅未来 National-5 全国数据入库后且将哨兵 `level` 设为 `province` 时）：「全国」会作为省级出现在指挥大屏地图，但名称不匹配 GeoJSON 省要素→不着色、不崩溃。**本阶段不入库全国数据，无现网影响。**

### B.4 风险说明
| 风险点 | 评估 |
|--------|------|
| 外键问题 | 无（仅新增合法目标） |
| 聚合异常 | 无（哨兵 id 未出现在任何计数序列） |
| 前端展示异常 | 无（无数据指向哨兵） |
| 重复插入 | 由 `code` UNIQUE 兜底 + 写入前存在性检查双重防护 |
| 回滚 | `DELETE FROM regions WHERE code='000000'`（单条、可回滚） |

**结论**：新增一条 regions 哨兵行，在当前（无全国数据）状态下对聚合/前端/外键 **零异常风险**。

---

## C. 当前 region code 规范确认

| 层级 | 现有 code 示例 |
|------|----------------|
| 省 | `130000` |
| 市 | `131000`、`130100` … |
| 县 | `131028`、`131081` … |

- 均为 **6 位 GB/T 2260 行政区划码**，前缀 `13` = 河北省。
- `000000` 不符合 `13xxxx` 真实编码体系，但：
  1. 长度同为 6 位，与现有体系格式兼容；
  2. `_province_code("000000")` → `"000000"`，与任何真实省前缀（`13`/`44`/…）**不冲突**，独立成键；
  3. 全零哨兵语义清晰（"全国" = 未限定具体行政区）。

### 候选评估
| 候选 | 是否冲突 | 推荐 |
|------|----------|------|
| `000000` | 不冲突（key=`000000`） | ✅ **推荐**（任务指定；全零哨兵最直观） |
| `999999` | 不冲突 | 备选（"最大码"语义不如全零清晰） |
| `100000` | 不冲突 | 备选（易与北京 `110000` 前缀混淆，不推荐） |

**采用**：`code = "000000"`（任务指定 + 上述理由）。

---

## 审计结论

1. `regions` 表可安全新增一条哨兵行，`code='000000'` 当前不存在、UNIQUE 约束不冲突。
2. 新增行在「无全国数据」状态下对 FK / 聚合 / 前端 **零影响**。
3. 采用 `code='000000' name='全国'`，`level` 按现有体系取 `province`（全国=行政区划树最顶层，类比省级 `parent_code` 为空），`parent_code=NULL`。
4. 模型无 `enabled` 字段 → 无需处理 enabled 状态；全国身份完全由固定 `code` 表达，**不新增 `national`/`is_national` 列**。

**审计通过，可进入 Step 3 最小实施。**
