# Phase8-B-2 运行版本一致性检查报告

检查时间：2026-07-29 16:10（Asia/Shanghai）。  
性质：只读进程、代码和生产运行记录检查。

## 1. 结论

当前大厂政府网站的 fetch 调用契约在实际运行中已一致，未发现多实例监听、旧 uvicorn 残留或重复部署目录。此前错误对应的是历史运行时版本漂移；当前运行版本已在 16:00 的真实调度中成功抓取 20 条原始内容。

历史事故等级：P1。当前残余风险：P2。  
是否需要代码修复：本次检查未发现需要再改业务代码的缺陷；应保留现有兼容测试，并在发布流程中保留进程重启与运行后验证。

## 2. 运行进程证据

|项|证据|
|-|-|
|父启动进程|PID 34256；2026-07-29 15:51:56 启动；`C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`|
|实际监听子进程|PID 32456；父 PID 34256；同一启动命令；唯一监听 `0.0.0.0:8000`|
|解释器路径|虚拟环境入口为 `backend\.venv\Scripts\python.exe`；实际进程镜像为其 venv 基解释器 `C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe`，与 `pyvenv.cfg` 一致|
|多 uvicorn 实例|未发现。命令行出现的两个 Python 进程为同一次启动的父/子关系，只有 PID 32456 监听 8000|
|旧进程残留|未发现其他 `uvicorn app.main:app` 命令或其他 8000 监听者|
|部署目录|工作区内只发现一套 `backend\app\main.py`、`backend\app\collectors\service.py`、`backend\app\collectors\government_collector.py`|

Windows 从进程外不能安全、无侵入地枚举 Python `sys.modules` 的每个 `.py` 路径；因此“loaded module path”以启动命令、唯一源码路径、源码时间戳和真实运行结果交叉验证，而不做进程注入或调试附加。

## 3. 调用签名核验

当前源码：

```python
GovernmentCollector.fetch(self, keywords=None, region_kw=None, topic_kw=None)
```

当前 `CollectorService` 调用：

```python
collector.fetch(keywords=monitoring_kw, region_kw=region_kw, topic_kw=topic_kw)
```

三个关键字参数完全一致，均被 `GovernmentCollector.fetch` 接受；`region_kw/topic_kw` 在该政府源中仅为接口兼容参数，不参与过滤。

## 4. 时间与真实运行验证

|项目|时间/结果|
|-|-|
|`government_collector.py` 最后修改|2026-07-28 22:16:36|
|`government_collector.cpython-313.pyc`|2026-07-28 22:17:35|
|`service.py` 最后修改|2026-07-29 14:07:19|
|当前 uvicorn 启动|2026-07-29 15:51:56，晚于上述源码修改|
|启动后首个大厂调度运行|2026-07-29 16:00:00|
|该运行结果|`status=success`、`fetched_raw=20`、`created=0`、`failed=0`、`error_msg=NULL`|

这条 16:00 运行直接证明当前监听服务已成功执行带 `region_kw/topic_kw` 的统一调用，没有重现历史 `TypeError`。

## 5. 后续建议

1. 保留并持续执行 `test_government_collector_compat.py`，该测试已覆盖签名兼容和“参数不改变政府源全量采集”。
2. 每次发布后至少观察一个调度周期：目标为大厂运行无 `TypeError` 且 `fetched_raw>0`。
3. 不建议为此新增运行时热补丁、第二个 uvicorn 实例或代码分支；当前证据支持维持单实例部署。

