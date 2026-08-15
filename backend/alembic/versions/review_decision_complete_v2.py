"""review_decision_complete_v2

上一版迁移（review_substates_v1）已把模型 review_decision 的 CHECK 约束
收窄语义、允许 'complete_review'，但遗漏了数据库侧实际约束的同步修改：
数据库中的 ck_*_manual_reviews_decision 仍只允许原始的 5 个取值，
导致「完成复核」写入 review_decision='complete_review' 时触发
CheckViolation。本迁移补齐：删除旧约束、重建包含 'complete_review' 的新约束。

Revises: review_substates_v1
"""
from typing import Sequence, Union

from alembic import op

revision = "review_decision_complete_v2"
down_revision = "review_substates_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("foreign_manual_reviews", "domestic_manual_reviews")
_OLD_CHECK = (
    "review_decision IS NULL OR review_decision IN "
    "('keep_rule','use_ai_display','confirm_event_change','confirm_alert_change','reject_change')"
)
_NEW_CHECK = (
    "review_decision IS NULL OR review_decision IN "
    "('keep_rule','use_ai_display','confirm_event_change','confirm_alert_change','reject_change','complete_review')"
)


def upgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"ck_{table}_decision", table, type_="check")
        op.create_check_constraint(f"ck_{table}_decision", table, _NEW_CHECK)


def downgrade() -> None:
    for table in _TABLES:
        op.drop_constraint(f"ck_{table}_decision", table, type_="check")
        op.create_check_constraint(f"ck_{table}_decision", table, _OLD_CHECK)
