"""初始化数据脚本（种子数据）。

用法（在 backend/ 目录下执行）：
    python scripts/init_db.py

前置：先执行 `alembic upgrade head` 创建表结构。
本脚本写入种子数据（幂等）：
    - 管理员 admin / admin123（bcrypt 加密，禁止明文）
    - 区域：大厂回族自治县（code=131028, level=county）

说明：脚本开头调用 Base.metadata.create_all 作为安全网，
      即使未执行 Alembic 也能建表；与 Alembic 共存无冲突。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保 backend/ 在 sys.path，便于直接运行脚本
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
import app.models  # noqa: F401  注册模型
from app.models.user import User
from app.models.region import Region
from app.models.keyword import Keyword


# 默认敏感词种子（仅数据，不改表结构）。
# 说明：MVP 阶段 RuleFallbackProvider 使用内置 DEFAULT_KEYWORDS；
# 此处把 keywords 表填好，作为「可扩展数据库 keywords」的未来扩展入口
# （后续可经 AIService 构造参数注入，本阶段不消费）。
DEFAULT_KEYWORDS = [
    ("火灾", 8, "安全事故"),
    ("爆炸", 9, "安全事故"),
    ("事故", 6, "安全事故"),
    ("伤亡", 9, "安全事故"),
    ("死亡", 8, "安全事故"),
    ("冲突", 7, "社会稳定"),
    ("群体", 7, "社会稳定"),
    ("上访", 8, "社会稳定"),
    ("维权", 6, "社会稳定"),
    ("投诉", 4, "民生服务"),
    ("谣言", 8, "网络舆情"),
    ("诈骗", 8, "违法犯罪"),
    ("腐败", 7, "廉政风险"),
    ("贪污", 7, "廉政风险"),
    ("涉警", 8, "涉警舆情"),
    ("舆情", 3, "网络舆情"),
]


def _seed_keywords(db) -> None:
    for word, weight, category in DEFAULT_KEYWORDS:
        exists = db.query(Keyword).filter(Keyword.word == word).first()
        if exists is None:
            db.add(Keyword(word=word, weight=weight, category=category))
            print(f"[init_db] 已插入敏感词: {word} (weight={weight})")
        else:
            print(f"[init_db] 敏感词已存在，跳过: {word}")


def init() -> None:
    # 安全网：确保表存在（幂等）
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 管理员（bcrypt 加密）
        admin = db.query(User).filter(User.username == settings.init_admin_username).first()
        if admin is None:
            db.add(
                User(
                    username=settings.init_admin_username,
                    password_hash=hash_password(settings.init_admin_password),
                    role="admin",
                )
            )
            print(f"[init_db] 已创建管理员用户: {settings.init_admin_username}")
        else:
            print(f"[init_db] 管理员用户已存在，跳过: {settings.init_admin_username}")

        # 区域：大厂回族自治县
        region = db.query(Region).filter(Region.code == "131028").first()
        if region is None:
            db.add(Region(code="131028", name="大厂回族自治县", level="county"))
            print("[init_db] 已插入区域: 大厂回族自治县 (131028, county)")
        else:
            print("[init_db] 区域已存在，跳过: 大厂回族自治县")

        # 敏感词表（规则降级与命中统计的扩展入口）
        _seed_keywords(db)

        db.commit()
        print("[init_db] 初始化完成。")
    except IntegrityError:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init()
