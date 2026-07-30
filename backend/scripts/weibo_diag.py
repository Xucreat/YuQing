"""微博八爪鱼 API 原始响应诊断（不入库、不消费）。"""
import os
import sys
import json

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.config import settings
from app.collectors.weibo_octopus_collector import WeiboOctopusCollector

c = WeiboOctopusCollector(mark_exported=False)
print("base_url =", c.base_url)
print("task_id  =", c.task_id)
print("api_key set =", bool(settings.bazhu_api_key), "| user/pass set =",
      bool(settings.bazhu_username and settings.bazhu_password))

try:
    token = c._get_token()
    print("token len =", len(token), "prefix =", token[:6] + "...")
except Exception as e:
    print("TOKEN ERROR:", repr(e))
    sys.exit(1)

# 原始拉取
resp = c.session.get(
    f"{c.base_url}{c.path_notexported}",
    params={"taskId": c.task_id, "size": c.fetch_size},
    headers={"Authorization": f"Bearer {token}"},
    timeout=c.timeout,
)
print("HTTP status =", resp.status_code)
body = resp.text
print("body length =", len(body))
print("body head   =", body[:1500])
# 尝试解析结构
try:
    j = resp.json()
    print("json top keys =", list(j.keys()) if isinstance(j, dict) else type(j))
    print("json sample   =", json.dumps(j, ensure_ascii=False)[:1500])
except Exception as e:
    print("json parse error:", repr(e))
