# MediaCrawler 多关键词轮询实施文档

## 1. 实施目标

解决 `weibo_mediacrawler` 在 `config_json.keywords=[]` 时，将所有启用监测关键词一次性传给 MediaCrawler、再由单个 `max_items=20` 总量截断的问题。

本次采用最小化改动方案：

- 每次调度只选择一个启用关键词；
- 每次仍最多抓取 `max_items` 条，当前配置为 20；
- 采集完成后推进关键词游标；
- 采集失败时不推进游标；
- 继续复用现有的 JSONL 解析、微博去重、入库和调度锁。

## 2. 生效范围

仅对 `data_source.key = 'weibo_mediacrawler'` 生效。

以下行为保持不变：

- `config_json.keywords` 非空时，仍使用数据源自己的关键词列表；
- `config_json.keywords=[]` 时，使用全局已启用监测关键词；
- `max_items` 仍是单次采集总量上限，取值范围仍为 1 到 20；
- 手动直接调用 collector、fixture 测试和没有对应 `data_sources` 行的旧式调用不启用持久化轮询；
- 数据库已有微博数据和去重逻辑不变。

## 3. 当前配置

`weibo_mediacrawler` 保持以下配置即可，不需要增加新配置键：

```json
{
  "collector": "mediacrawler",
  "platform": "weibo",
  "keywords": [],
  "max_items": 20,
  "collection_scope": "national"
}
```

当 `keywords` 为空时，系统读取 `keywords` 表中 `type='monitoring'` 且 `is_enabled=true` 的关键词。

## 4. 轮询算法

数据源新增持久化字段：

```text
data_sources.keyword_cursor
```

默认值为 `0`，表示从有效关键词列表的第一个关键词开始。

假设有效关键词按系统返回顺序为：

```text
[A, B, C]
```

轮询过程为：

```text
cursor=0 -> 抓取 A -> 保存 cursor=1
cursor=1 -> 抓取 B -> 保存 cursor=2
cursor=2 -> 抓取 C -> 保存 cursor=0
```

关键词列表会先去空、去重，并保留原有顺序。游标始终按当前关键词数量取模，因此关键词增删后不会越界。

注意：系统保证每个关键词都会获得搜索机会，但不能保证每个关键词一定返回微博数据。返回结果仍取决于微博是否存在匹配内容、登录状态、平台限流等因素。

## 5. 代码变更

### 5.1 数据库模型

修改：

`backend/app/models/data_source.py`

新增：

```python
keyword_cursor: Mapped[int] = mapped_column(
    Integer, nullable=False, default=0, server_default="0"
)
```

### 5.2 数据库迁移

新增：

`backend/alembic/versions/p32_mediacrawler_keyword_cursor.py`

迁移内容：

- `data_sources` 新增 `keyword_cursor INTEGER NOT NULL DEFAULT 0`；
- downgrade 时删除该字段。

当前数据库迁移状态：

```text
p32_mediacrawler_keyword_cursor (head)
```

### 5.3 采集服务

修改：

`backend/app/collectors/service.py`

新增：

- `select_round_robin_keyword()`：负责规范化关键词、按游标选择一个关键词；
- `_mediacrawler_keyword_turn()`：读取数据源配置和持久化游标；
- `_persist_mediacrawler_cursor()`：采集流程完成后保存下一个游标。

MediaCrawler 的采集分支现在只向 runner 传递当前轮次的一个关键词。

### 5.4 MediaCrawler Collector

修改：

`backend/app/collectors/media_crawler_weibo_collector.py`

新增可选参数：

```python
keyword_override
```

该参数仅用于调度层传递当前轮次关键词。直接调用 collector 时不传该参数，原有关键词解析行为保持不变。

运行配置和日志额外记录：

```text
effective_keywords_source=round_robin
selected_keywords=[当前关键词]
```

## 6. 成功与失败语义

### 成功

MediaCrawler 完成运行并进入现有入库流程后，保存下一个关键词游标。

### 抓取异常

例如命令启动失败、超时、输出文件缺失等情况：

- 当前关键词游标不推进；
- 下一次调度继续重试当前关键词；
- 现有 `CollectorRun(status='failed')` 和错误日志逻辑不变。

### 入库或分析部分失败

MediaCrawler 已成功返回数据时仍推进游标，避免同一批数据导致关键词长期卡住。单条分析失败仍按现有逻辑记录为部分失败。

## 7. 调度频率估算

每个关键词的轮询周期约为：

```text
数据源调度间隔 × 启用关键词数量
```

例如：

| 启用关键词数 | 调度间隔 | 单关键词约多久轮到一次 |
|---:|---:|---:|
| 5 | 60 分钟 | 5 小时 |
| 10 | 60 分钟 | 10 小时 |
| 20 | 60 分钟 | 20 小时 |

如果希望每个关键词每天至少轮到一次，调度间隔可按下面公式估算：

```text
调度间隔 ≤ 1440 / 启用关键词数量（分钟）
```

仍需遵守系统当前调度最小间隔 5 分钟及平台限流约束。

## 8. 验证结果

已执行：

```text
python -m compileall
alembic heads
alembic upgrade head
pytest -q tests/test_media_crawler_2a.py
pytest -q tests/test_media_crawler_1c.py tests/test_media_crawler_2d.py
pytest -q tests/test_media_crawler_adapter.py
pytest -q tests/test_media_crawler_2a.py tests/test_media_crawler_2d.py
```

结果：

- 新增及相关轮询测试：通过；
- MediaCrawler 运行器测试：通过；
- MediaCrawler 适配器测试：通过；
- 最后一次组合测试：17 passed。

数据源调度测试单独执行时在测试数据库流程中超过 120 秒，未获得通过结果；该问题未表现为本次 MediaCrawler 轮询测试失败，建议后续单独检查测试库连接或锁等待。

## 9. 回滚方式

代码回滚后，如数据库仍保留新增字段，不会影响旧逻辑；旧版本代码不会读取该字段。

如需完全回滚数据库结构：

```powershell
cd C:\Users\Administrator\Desktop\YQ\backend
alembic downgrade p12_datasource_schedule
```

执行数据库 downgrade 前应先停止调度器，并确认没有正在运行的 MediaCrawler 任务。

