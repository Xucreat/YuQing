# Phase DataSource-National-Mode-4 只读审计报告（PreAudit）

> 阶段目标：让 `collection_mode="national"` 的数据源真正「主题命中即可入库」，
> 无地域全国稿使用 `region_id=全国哨兵(id=24)` 承载。
> 本审计**只读**，未修改任何代码 / 数据库 / 表结构 / 前端 / migration。

---

## 审计范围与结论总览

| 审计项 | 结论 |
|--------|------|
| OpinionRegionService.decide 当前分支 | 已定位 national+无地域 → `rejected_no_monitoring_region_hit`（region_id=None） |
| OpinionAdmissionService 当前拒绝点 | `national_source_requires_region_relevance`（national 且无 region_hits → 拒） |
| Collector 过滤链 topic_only 支持 | `matches_region_topic` **已支持** `topic_only`（Phase Config-1），**无需修改** |
| 入库链路 region_id 落点 | `service.py:507` `region_id=region_decision.region_id`（NOT NULL，已有哨兵兜底） |
| collection_mode 在采集链路的可达性 | `collector.source_config.collection_mode()`（registry 注入，National-3 已就绪） |
| decide / evaluate 调用方数量 | 各 1 处（均 `service.py`），新增可选参数向后兼容 |

---

## 1. OpinionRegionService（opinion_region_service.py）

### 1.1 decide 完整分支（当前代码）
```
decide(db, item, *, scope_region_codes=None):
    national = not normalize_scope_codes(scope_region_codes)   # 空 scope → national
    hits = _region_hits(text, is_local_source=not national)
    if hits:                          # 任一地域命中 → 按廊坊层级绑定真实 region_id（accepted_*）
        ... return RegionDecision(region_id=<真实地域>, accepted=True)
    if national:
        return RegionDecision(None, hits, "rejected_no_monitoring_region_hit", ..., True)  # ★ 拒绝点
    default_region = _default_scope_region(db, scope_codes)   # 区域源无命中 → 用 scope 默认区域
    if default_region is None:
        return rejected_scope_region_not_found
    return accepted_scope_default (region_id=scope 默认)
```

### 1.2 national 无地域被拒的根因
- `national` 完全由「`scope_region_codes` 为空」隐式推断（National-3 之前的唯一通道）。
- 无地域命中时，分支落入 `if national:` → 直接 `region_id=None` + `rejected`。
- 而 `Opinion.region_id` 为 NOT NULL，因此即便放行也会撞物理约束 → 当前全国性主题稿（无地域）无法入库。

### 1.3 修复落点（设计，非实施）
新增 `collection_mode` 入参：
- `collection_mode == "national"` → `national = True`（显式覆盖，替代空 scope 隐式推断）。
- 无地域命中分支区分两种 national：
  - **显式 national**（`collection_mode=="national"`）：调用 `resolve_national_region(db)` 取哨兵 id，返回 `accepted_national_sentinel`，`region_id=全国`。
  - **隐式 national**（空 scope 但无显式 mode，即历史 4 个 national-scope 源未配置 mode 时）：保持原有 `rejected`（**生产行为零变化**）。

---

## 2. OpinionAdmissionService（opinion_admission_service.py）

### 2.1 当前拒绝点（evaluate）
```
if source_type != "weibo_post":
    if is_national and not region_hit_list:
        return rejected  # policy=national_source_requires_region_relevance   ★ 拒绝点
    return accepted (default_allow_non_weibo)
```
- `is_national` 由 `national_source`（=region_decision.national_source）或 `is_national_scope(source_scope_codes)` 确定。
- 因此 national 源即使主题命中，只要无地域命中 → 在准入层被拒（与 region_decision 双拒）。

### 2.2 修复落点（设计）
新增 `collection_mode` 入参，在 `is_national and not region_hit_list` 判断**之前**插入：
```
if collection_mode == "national":
    # 全国模式：地域相关性非必需；采集阶段已完成 topic_only 过滤
    return accepted  # policy=national_mode_topic_accepted
```
- regional / 隐式 national / weibo 路径**完全不变**。
- 仅显式 `collection_mode=="national"` 走新准入。

---

## 3. Collector 过滤链（common.py）

- `matches_region_topic(text, region_kws, topic_kws, match_mode="topic_only")` **已实现** `topic_only` 分支：
  > 纯主题模式：不要求地域命中；主题词为空时 fail-safe 拦截（避免无条件放行）。
- `topic_only` 由 `config_json.filter_mode` 驱动，采集器在 `fetch()` 内调用。
- **结论**：National-4 不需要修改 `common.py` / 任何 collector 执行逻辑——national 源的 `filter_mode=topic_only` 已能正确完成「主题命中即放行、无主题即拦截」。

---

## 4. 入库链路（service.py）

### 4.1 当前调用（_process_collector，line 475/480）
```python
region_decision = region_resolver.decide(
    db, item, scope_region_codes=getattr(collector, "scope_region_codes", None))
admission_result = admission.evaluate(
    item, region_keywords=region_kw, topic_keywords=topic_kw,
    collector_name=collector.source_name,
    source_scope_codes=getattr(collector, "scope_region_codes", None),
    national_source=region_decision.national_source, region_hits=region_decision.region_hits)
if not admission_result.accepted or not region_decision.accepted:
    admission_filtered += 1; continue
...
opinion = Opinion(..., region_id=region_decision.region_id, ...)   # NOT NULL
```

### 4.2 修改落点（设计）
- 从 `collector.source_config`（registry 注入的 `DataSourceConfig`）读取 `collection_mode`：
  ```python
  src_cfg = getattr(collector, "source_config", None)
  collection_mode = src_cfg.collection_mode() if src_cfg is not None else None
  ```
- 透传给 `decide(..., collection_mode=collection_mode)` 与 `evaluate(..., collection_mode=collection_mode)`。
- `region_id` 落点不变（仍取 `region_decision.region_id`）；显式 national 无地域时该值已为哨兵 id=24。

---

## 5. 红线符合性预审

| 红线 | 是否满足 |
|------|----------|
| 不改 Opinion/Event/Risk 模型 | ✅ 仅改 service 调用透传 + 两 service 分支逻辑 |
| 不放开 region_id nullable | ✅ 仍写合法 region_id（哨兵 24 或真实地域） |
| 不改 scheduler/registry/collector 调度逻辑 | ✅ 仅新增可选参数透传 |
| 不新增字段/表/migration | ✅ |
| 不改 dashboard 聚合 / 前端 | ✅ |
| 不引入 Redis/ES/MQ/Celery | ✅ |
| Event/Risk 链路不变 | ✅ region_id 仍是合法外键，聚合零影响 |
| 历史数据不修改 | ✅ 验证脚本只读，不 UPDATE opinions / 不重跑采集 |
| 仅影响未来采集 | ✅ 哨兵兜底只在 collection_mode=="national" 显式声明时激活 |

---

## 6. 审计结论

1. 两道拒绝闸门（`region_decision` 与 `admission`）均定位清晰，且仅各 1 处调用方 → 改动面极小、向后兼容。
2. `topic_only` 过滤在采集层已就绪，National-4 无需触碰 collector / common.py。
3. `collector.source_config` + `resolve_national_region` + 哨兵 Region(24) 三件套已就位，可直接组成「national 主题稿 → region_id=24 → 入库」链路。
4. 隐式 national（空 scope 未配 mode）保持旧拒绝行为，**不影响当前 38 个数据源的生产采集**。

**审计通过，可进入 Step 2 最小实施。**
