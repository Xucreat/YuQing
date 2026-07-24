"""只读接口测试：预警记录列表筛选（status / exclude_status）。

仅调用运行中的后端 GET /api/alerts/records，不写库。
用应用自身 JWT 密钥为管理员签发测试 token（operator 本地自测）。
"""
import sys, json, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

sys.path.insert(0, r"C:\Users\Administrator\Desktop\YQ\backend")
from app.core.config import settings
from app.core.security import create_access_token
import psycopg

# 1) 取一个有效用户 id（优先 superuser）
conn = psycopg.connect("postgresql://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db")
cur = conn.cursor()
cur.execute("SELECT id FROM users WHERE is_superuser=true ORDER BY id LIMIT 1")
uid = cur.fetchone()[0]
conn.close()
print(f"[token] 为 user id={uid} 签发测试 JWT (secret={settings.secret_key[:6]}...)")

token = create_access_token(subject=uid, expires_minutes=30, extra_claims={"role": "superuser", "role_name": "superuser"})
BASE = "http://127.0.0.1:8000/api/alerts/records"

def call(params: dict):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}?{qs}" if qs else BASE
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def summarize(label, params):
    code, body = call(params)
    if code != 200:
        print(f"\n### {label}  params={params}\n  HTTP {code}: {body[:200]}")
        return code, body
    items = body["items"]
    stat = {}
    for it in items:
        stat[it["status"]] = stat.get(it["status"], 0) + 1
    fp = stat.get("false_positive", 0)
    print(f"\n### {label}  params={params}")
    print(f"  HTTP {code}  total={body['total']}  returned={len(items)}  status_breakdown={stat}")
    print(f"  false_positive 在结果中: {fp} 条  -> {'PASS 不显示' if (fp==0) else 'FAIL 出现误报' if 'exclude' in label or (params.get('exclude_status')) else '（预期可见）'}")
    return code, body

print("="*70)
print("场景1：前端默认（发送 exclude_status=false_positive）—— 误报应不显示")
summarize("场景1 默认隐藏误报", {"exclude_status": "false_positive", "page": 1, "size": 100})

print("="*70)
print("场景2：关闭隐藏误报（不发 exclude_status）—— 误报应可见")
summarize("场景2 显示全部", {"page": 1, "size": 100})

print("="*70)
print("场景3：status=false_positive —— 仅误报")
summarize("场景3 仅误报", {"status": "false_positive", "page": 1, "size": 100})

print("="*70)
print("场景4：status=resolved —— 仅已解决")
summarize("场景4 仅已解决", {"status": "resolved", "page": 1, "size": 100})

print("="*70)
print("场景5a：risk_level=critical 筛选")
summarize("场景5a risk_level=critical", {"risk_level": "critical", "page": 1, "size": 100})

print("="*70)
print("场景5b：handled=false（未处理）+ 分页 size=5")
code, body = call({"handled": "false", "page": 1, "size": 5})
print(f"  HTTP {code} total={body.get('total')} returned={len(body.get('items', []))} (分页 size=5)")

print("="*70)
print("附加：非法 status 值应返回 422")
code, body = call({"status": "bogus_value"})
print(f"  HTTP {code}  -> {'PASS 422' if code==422 else 'FAIL'}  detail={str(body)[:120]}")

print("="*70)
print("附加：非法 exclude_status 值应返回 422")
code, body = call({"exclude_status": "xyz"})
print(f"  HTTP {code}  -> {'PASS 422' if code==422 else 'FAIL'}  detail={str(body)[:120]}")
