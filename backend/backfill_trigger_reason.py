"""一次性回填：将库中已有英文 trigger_reason 改写为中文。

仅做文本正则改写，不改变任何业务语义；可重复运行（幂等）。
"""
import re
from app.db.session import SessionLocal
from app.models.alert import AlertRecord


def to_chinese(reason: str) -> str:
    if not reason:
        return reason
    # risk_score(85)>=threshold(80) -> 风险评分 85 达到预警阈值 80
    reason = re.sub(
        r"risk_score\((\d+)\)>=threshold\((\d+)\)",
        r"风险评分 \1 达到预警阈值 \2",
        reason,
    )
    # keywords matched: a,b -> 命中关键词：a、b
    reason = re.sub(r"keywords matched:\s*(.+)", lambda m: "命中关键词：" + m.group(1), reason)
    # source matched: x -> 命中来源：x
    reason = re.sub(r"source matched:\s*(.+)", lambda m: "命中来源：" + m.group(1), reason)
    # 统一分隔符为中文顿号/分号
    reason = reason.replace(",", "、").replace("; ", "；")
    return reason


def main():
    db = SessionLocal()
    try:
        rows = db.query(AlertRecord).all()
        updated = 0
        for r in rows:
            new_r = to_chinese(r.trigger_reason)
            if new_r != r.trigger_reason:
                r.trigger_reason = new_r
                updated += 1
        db.commit()
        print(f"total={len(rows)} updated={updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
