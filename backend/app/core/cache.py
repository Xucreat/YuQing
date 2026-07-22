"""轻量级进程内 TTL 缓存（用于 dashboard 等只读聚合接口的轮询减负）。

设计约束与限制：
- 不引入 Redis：当前项目仅依赖 PostgreSQL，无 Redis 基础设施。
- 进程内字典缓存：每个 uvicorn worker 各自持有一份，TTL 到期自动失效。
- 多 worker 限制：每个 worker 独立缓存、互不共享。N 个 worker 各自有各自的命中，
  整体命中率随 worker 数线性下降，但数据正确性不受影响（每次过期都会重新查库）。
  若未来部署多 worker 且希望统一缓存，应改为 Redis 等共享缓存（见下方 TODO）。
- 不缓存用户私有权限数据：dashboard 接口返回的是全局聚合数据（与具体登录用户无关），
  所有已认证用户看到的结果一致，因此跨用户复用缓存是安全的。
- 缓存 key 必须包含全部影响结果的参数（days / limit 等），避免不同参数串缓存。
- 三类端点（stats / recent / alerts / hot-keywords）使用不同 key 前缀，互不污染。

用法：
    key = f"dash:stats:{days}"
    cached = cache_get(key)
    if cached is not None:
        return cached
    data = _compute(...)
    cache_set(key, data)
    return data
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

# 默认 TTL：10s。低于大屏 15-30s 轮询间隔，保证数据新鲜度的同时减轻数据库压力。
DEFAULT_TTL: float = 10.0

# 模块内字典：key -> (写入时间戳, 值)。进程级，非线程安全但 CPython GIL 下足够。
_store: Dict[str, Tuple[float, Any]] = {}


def cache_get(key: str, ttl: float = DEFAULT_TTL) -> Optional[Any]:
    """返回未过期的缓存值；不存在或已过期返回 None（并顺手清理过期项）。"""
    item = _store.get(key)
    if item is None:
        return None
    ts, val = item
    if time.time() - ts > ttl:
        _store.pop(key, None)
        return None
    return val


def cache_set(key: str, val: Any, ttl: float = DEFAULT_TTL) -> None:
    """写入缓存。值应为可安全跨请求复用的纯数据（dict / list / 基础类型）。"""
    _store[key] = (time.time(), val)


def cache_keys() -> List[str]:
    """返回当前所有缓存 key（仅用于观测与测试，不影响业务逻辑）。"""
    return list(_store.keys())


def cache_clear() -> None:
    """清空全部缓存（测试夹具或手动失效用）。"""
    _store.clear()
