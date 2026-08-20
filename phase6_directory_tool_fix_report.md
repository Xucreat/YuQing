# Phase 6 阶段二：历史 incoming 处置工具修复报告

生成时间：2026-08-19 16:32

## 结论先行

修复了 Phase 5 的两个缺陷：
1. `load_run_status()` 不再无条件返回空字典，改为返回 `(mapping, available)`，映射不可用时显式标记 `mapping_unavailable`，文件判为 `manual_review`（需人工对账），**绝不误判为可归档孤立文件**。
2. `--apply` 不再隐式移动 `manual_review`，改为**显式文件选择 + 显式 `--allow-manual-review-move` 标志**才移动；`weibo_do_not_touch`/`keep` 永不移动。

21 个测试全绿。

## 修复内容

### 1. `classify_file(source_key, run_status, mapping_available=True)`
- 新增 `mapping_available` 参数：False 时返回 `manual_review`（mapping_unavailable），不再返回 `quarantine_candidate`。

### 2. `load_run_status(classification_path=None) -> (mapping, available)`
- 默认返回 `({}, False)`（映射不可用），调用方必须按「需人工对账」处理。
- 显式传入 `--classification`（Phase 4 对账 JSON）时返回 `(mapping, True)`。

### 3. `apply_plan(..., selected_files, allow_manual_review_move, operator)`
- 仅移动「显式指定文件」且 category 允许的文件；
- `quarantine_candidate`：需 `selected_files` 显式指定；
- `manual_review`：需 `selected_files` + `allow_manual_review_move=True`；
- `weibo_do_not_touch` / `keep`：永不移动；
- 审计字段补全：source/target/category/manifest_id/task_id/sha256/operator/command/timestamp/rollback status。

### 4. CLI 新增
`--classification`、`--files`（显式文件清单，--apply 必填）、`--allow-manual-review-move`。

## 测试结果

21 passed / 0 failed，覆盖 Phase 6 要求的全部场景：
- mapping 不可用不误判 orphan / mapping 缺失保持原位
- manual_review 默认不移动 / 需 allow 标志
- quarantine 需显式文件 / weibo 永不移动 / keep 永不移动
- SHA256 不匹配拒绝 / 目标存在拒绝 / 中途回滚 / 超批拒绝
- load_run_status 默认不可用 + 显式 classification 可用

## 未执行

未对任何真实 incoming 文件执行 `--apply`（仅 dry-run 测试，用 tmp 目录 fixture）。
