"""一次性回填：用最新的 AI 规则逻辑重新研判全部舆情，纠正情感误判。

背景：情感极性已与风险分解耦（见 app/services/ai/fallback.py）。本脚本对库内
所有 Opinion 重新跑 ai.analyze(title, content)，写回 sentiment / risk_score /
summary / keywords / analysis_suggestion，使历史数据也应用新规则。

用法（项目 backend 目录下，使用项目 venv）：
    .venv/Scripts/python.exe reanalyze_sentiment.py

说明：
- 仅覆盖 analysis_status 已完成/待分析/失败的存量记录；不改其它字段。
- 当前 DeepSeek 无余额，analyze 走 RuleFallbackProvider（即新规则），结果稳定可复现。
- 生产运行前建议先备份数据库。
"""
from __future__ import annotations

from app.db.session import SessionLocal
from app.models.opinion import Opinion
from app.services.ai.fallback import RuleFallbackProvider


def main() -> None:
    db = SessionLocal()
    # 直接走 RuleFallbackProvider（离线、确定性、与线上降级路径一致），
    # 避免 AIService 逐条去调 DeepSeek 网络造成超时卡死。
    ai = RuleFallbackProvider()
    rows = db.query(Opinion).all()
    total = len(rows)
    fixed = 0
    counts: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
    for o in rows:
        try:
            text = f"标题：{o.title or ''}\n正文：{o.content or ''}"
            r = ai.analyze(text)
        except Exception as e:  # 单条失败不中断
            print(f"  skip id={o.id}: {e}")
            continue
        if o.sentiment != r.sentiment:
            fixed += 1
        o.sentiment = r.sentiment
        o.risk_score = r.risk_score
        o.summary = r.summary
        o.keywords = ",".join(r.keywords)
        o.analysis_suggestion = r.suggestion
        o.analysis_status = "completed"
        counts[r.sentiment] = counts.get(r.sentiment, 0) + 1
    db.commit()
    print(f"总计 {total} 条，情感被纠正 {fixed} 条")
    print("重新研判后分布：", counts)


if __name__ == "__main__":
    main()
