# Phase MediaCrawler Platform-2-B1

## Status

`IMPLEMENTED`

当前状态：`READY_FOR_PLATFORM_2_B2`

本阶段仅实现 XHS（小红书）的 PlatformSpec、Normalizer 和 Registry/config contract skeleton。未实现 XhsCollector，未接入真实 CLI，未执行真实采集。

## 1. 修改文件

- `backend/app/collectors/mediacrawler_platform.py`
- `backend/app/collectors/mediacrawler_normalizers.py`
- `backend/app/collectors/registry.py`
- `backend/tests/test_media_crawler_xhs_platform.py`
- `backend/tests/fixtures/media_crawler/xiaohongshu.jsonl`
- `docs/Phase_MediaCrawler_Platform_2B1_Implementation_Report.md`

未修改 `models/`、`alembic/`、`scheduler.py`、`.env`、CollectorService、生产 DataSource 和微博兼容文件。

## 2. XHS 新增能力

新增 `XHS_PLATFORM_SPEC`，复用现有 `MediaCrawlerPlatformSpec` 和平台注册表：

- `platform=xiaohongshu`
- `source=xiaohongshu`
- `source_type=xhs_note`
- `normalizer_key=xiaohongshu`
- `cli_code=UNKNOWN`
- `crawler_type=UNKNOWN`
- `native_output_parts=()`
- `supported_login_types=空集合`
- `allow_real_collection=False`

未验证的 CLI、crawler type、登录方式和 native artifact 目录没有被猜测。XHS Spec 只能用于离线 contract/fixture 测试，不能作为真实运行授权。

新增 `XhsNormalizer` 并注册到 normalizer registry。支持离线 skeleton 字段：`note_id`、`desc`、`nickname`、`note_url`、`time`、`liked_count`、`comment_count`、`collected_count`、`share_count`。空正文返回 `None`；缺失的可选统一字段返回 `None`；互动数使用现有通用解析器。

Registry 仍通过 capability 识别 MediaCrawler；未知 platform 仍 fail closed。没有新增 XhsCollector 或 generic Collector 的 XHS 分支。

## 3. 微博兼容验证

- `MediaCrawlerWeiboCollector` class path 未修改；
- `WEIBO_PLATFORM_SPEC` 未修改；
- `weibo_mediacrawler` source key 未修改；
- 既有微博 fixture 测试仍保留并在本阶段测试中验证 class/spec 契约；
- 未修改微博 compatibility policy、artifact、profile、lock 或生产链路。

## 4. 测试结果

执行：

```powershell
python -m pytest -q backend/tests/test_media_crawler_xhs_platform.py
python -m pytest -q backend/tests/test_media_crawler_platform_1.py backend/tests/test_media_crawler_adapter.py
```

结果：

```text
backend/tests/test_media_crawler_xhs_platform.py: 9 passed
backend/tests/test_media_crawler_platform_1.py backend/tests/test_media_crawler_adapter.py: 15 passed
all `backend/tests/test_media_crawler*.py`: 144 passed
```

测试均为 fixture/config/registry/gate 离线测试，不启动 MediaCrawler。

## 5. 数据库影响

`NONE`。

没有新增字段、表或 migration，没有修改 `DataSource`、`CollectorRun` 或 `Opinion`。XHS 平台信息通过现有 `config_json.platform` 解析，不将命令、凭据或 profile path 放入配置。

## 6. 真实采集确认

- 未启动真实 MediaCrawler；
- 未执行真实小红书采集；
- 未启动 Scheduler；
- real-run gate 关闭测试确认不会启动注入的命令；
- 未修改 `.env`、生产配置或真实 DataSource。

## 7. 下一步建议

进入 `Platform-2-B2` 前，先基于锁定的 MediaCrawler 上游版本确认 XHS CLI code、crawler type、login policy、native output path 和真实 JSONL schema，再替换当前 `UNKNOWN` test-state contract。完成离线 fixture/argv/path/profile 隔离回归后，才可另行评估受控 real-run。
