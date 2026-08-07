# 小红书命名对齐 + 关键词清空 实施确认报告

> 日期：2026-08-07 | 阶段：Phase MediaCrawler 命名修复 + 关键词策略修正
> 身份门禁：`db_identity_check` → **VERIFIED**（opinions=1455≥100，退出码 0）→ 安全写库

## 一、改动清单

### ① 命名对齐（registry 装配）
- **文件**：`backend/app/collectors/registry.py`（`_build_collector`，MediaCrawler 分支）
- **改动**：新增一行
  ```python
  kwargs["source_name"] = meta.get("name")
  ```
  `meta["name"]` 来自 `data_sources.name`（registry.py:311 已构建），使写入 `collector_runs.collector_name` 直接等于数据源显示名。
- **作用域**：
  - 微博（子类 `MediaCrawlerWeiboCollector`，类属性 `source_name="微博（MediaCrawler）"`）传入同名值 → 无副作用；
  - 小红书（基类 `MediaCrawlerPlatformCollector`，原回退 `MediaCrawler[xiaohongshu]`）→ 被显式覆盖为 `小红书（MediaCrawler）`。

### ② 历史记录迁移（DB）
- `UPDATE collector_runs SET collector_name='小红书（MediaCrawler）' WHERE collector_name='MediaCrawler[xiaohongshu]'`
- 结果：**15 条迁移成功，旧名残留 0**。

### ③ 清空小红书 keywords（DB）
- 数据源 `xhs_mediacrawler`(id=45) `config_json.keywords`：`['大厂回族自治县']` → `[]`。
- 使其回退到第③级全局词（`get_monitoring_keywords` 读关键词管理启用词）。

## 二、重启加载新代码
- 从顶层祖先进程整树 `taskkill /PID 23664 /T /F`（早期误用 `//PID` 导致旧 8000 未被杀、反被机制重启为 45792 并持锁；已纠正）。
- 端口释放后，后台带 env 重启：
  ```
  cd backend && MEDIA_CRAWLER_CHECKOUT_ROOT="D:/code files/mediaCrawler/MediaCrawler" \
  MEDIA_CRAWLER_ROOT="D:/code files/mediaCrawler/MediaCrawler" \
  .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
- 新进程 **PID 42132**，启动日志**未**出现"未获调度锁"提示 → 成功获取 scheduler 单例锁（现唯一全量调度器）。

## 三、验证结果（全部 ✅）

| 验证项 | 方法 | 结果 |
|---|---|---|
| registry 命名对齐 | `resolve_collectors(xhs)` 检查 `collector.source_name` | `= '小红书（MediaCrawler）'` == `ds.name` ✅ |
| 关键词回退全局 | `resolve_effective_keywords(xhs)` | source=`global`，生效词 **44** 个（含大厂回族自治县/通山县）✅ |
| 历史迁移落库 | DB 计数 | 新名 15 / 旧名 0 ✅ |
| **运行服务端到端** | 强制 XHS 逾期 → 新建 run **15557** | `collector_name='小红书（MediaCrawler）'`、`trigger=scheduled` ✅ |
| 实跑闭环 | run 15557 终态 | `status=success`，`fetched_raw=20`，`created=20`，`duplicate=0` ✅ |
| 调度节拍 | 强制触发后 `next_collect_time` | 已重置未来（XHS 11:39 / +120min），正常 ✅ |

## 四、修复后的用户可见效果
- **数据源管理页**：小红书不再显示"从未运行"——`latest.get(ds.name)` 现能命中迁移后的 15 条记录（含最新一次成功 run），显示最近运行时间与状态。
- **关键词管理联动**：在关键词管理**新增并启用**"湖北通山县"等词后，小红书（与微博一样）将纳入全局词参与采集，不再只搜"大厂回族自治县"。

## 五、遗留耐久提示（非本次必改）
- `MEDIA_CRAWLER_CHECKOUT_ROOT` / `MEDIA_CRAWLER_ROOT` **仍仅进程注入**（未落 `.env`）。未来若以纯净命令重启 8000，微博/小红书子进程 `import config` 会再次失败。建议固化到 `.env` 或在 `mediacrawler_runtime.py:293` 的 `checkout_root` 回退链补 `media_crawler_root`。
- 小红书 profile 修复为**目录级 robocopy**（持久），无需 env。
