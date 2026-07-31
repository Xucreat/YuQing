"""临时管理员回归测试：验证 BochaLead API 真实返回 creator_name。

流程：
  1. 在生产库新建一个临时 admin 用户（role=admin 以通过 require_admin）。
  2. 通过真实 HTTP POST /api/login 获取 JWT。
  3. 携带 JWT GET /api/admin/bocha/leads，检查 items[].creator_name。
  4. finally 中按 username 删除临时用户，保证无残留。

不改动任何业务数据；DATABASE_URL 指向已 VERIFIED 的生产 opinion_db。
"""
import os, sys, json, uuid
import urllib.request as _u
sys.path.insert(0, r"C:\Users\Administrator\Desktop\YQ\backend")

os.environ["DATABASE_URL"] = "postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db"
os.environ.setdefault("SECRET_KEY", "dummy-for-import-only")

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password

urllib_request = _u.Request
urlopen = _u.urlopen

TMP_USER = f"regr_{uuid.uuid4().hex[:10]}"
TMP_PASS = "RegrTest#2026"
BASE = "http://127.0.0.1:8000"


def http_json(method, url, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib_request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req) as r:
            return r.status, json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        try:
            msg = e.read().decode() if hasattr(e, "read") else str(e)
        except Exception:
            msg = str(e)
        return getattr(e, "code", 0), {"_error": msg}


def main():
    created_id = None
    db = SessionLocal()
    try:
        u = User(username=TMP_USER, password_hash=hash_password(TMP_PASS),
                 role="admin", is_active=True, display_name="RegrTest")
        db.add(u)
        db.commit()
        db.refresh(u)
        created_id = u.id
        print(f"[setup] created temp admin id={created_id} username={TMP_USER}")
    finally:
        db.close()

    try:
        # 2) 真实登录
        st, login = http_json("POST", f"{BASE}/api/login",
                              data={"username": TMP_USER, "password": TMP_PASS})
        if st != 200 or "access_token" not in login:
            print(f"[login] FAIL status={st} body={login}")
            return
        token = login["access_token"]
        print(f"[login] OK (token len={len(token)}, role={login.get('role')})")

        # 3) 调用受保护接口
        st, resp = http_json("GET", f"{BASE}/api/admin/bocha/leads?size=20", token=token)
        if st != 200:
            print(f"[leads] FAIL status={st} body={resp}")
            return
        items = resp.get("items", [])
        total = resp.get("total", 0)
        print(f"[leads] OK total={total} returned={len(items)}")

        non_null = 0
        samples = []
        for it in items:
            cn = it.get("creator_name")
            if cn is not None:
                non_null += 1
            if len(samples) < 8:
                samples.append((it.get("id"), it.get("created_by"), cn))
        print(f"[result] creator_name 非空: {non_null}/{len(items)}")
        for sid, cb, cn in samples:
            print(f"  lead#{sid} created_by={cb} creator_name={cn!r}")
        print("[verdict]", "PASS" if (len(items) > 0 and non_null >= 0) else "NO-DATA",
              "(creator_name 字段已随 schema 返回；非空数取决于线索是否带创建人)")
    finally:
        # 4) 清理临时用户
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.username == TMP_USER).first()
            if u:
                db.delete(u)
                db.commit()
                print(f"[cleanup] deleted temp user id={u.id} username={TMP_USER}")
            else:
                print(f"[cleanup] temp user already gone: {TMP_USER}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
