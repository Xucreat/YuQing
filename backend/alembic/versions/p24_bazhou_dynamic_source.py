"""Restrict Bazhou government collection to the Bazhou Dynamic column."""

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p24_bazhou_dynamic_source"
down_revision: Union[str, None] = "p23_collector_run_duplicate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_CONFIG = {
    "source_name": "\u9738\u5dde\u5e02\u653f\u5e9c\u7f51-\u9738\u5dde\u52a8\u6001",
    "list_urls": ["https://www.bazhou.gov.cn/xwzx/bzdt"],
    "link_rule": {
        "href_regex": r"(?i)^/?xwzx/bzdt/content_\d+(?:\.html)?(?:\?.*)?$",
    },
    "max_articles": 10,
    "keywords": "\u9738\u5dde,\u5eca\u574a,\u6cb3\u5317",
    "content_selectors": ["div.nr"],
}


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT config_json FROM data_sources WHERE key = :key"),
        {"key": "bazhou_gov"},
    ).first()
    if not row:
        return

    try:
        current = json.loads(row[0] or "{}")
    except (TypeError, ValueError):
        return

    if not isinstance(current, dict):
        return

    # Do not overwrite a deliberate administrator customization.
    if current.get("list_urls") != ["https://www.bazhou.gov.cn"]:
        return
    if current.get("link_rule"):
        return

    conn.execute(
        sa.text(
            "UPDATE data_sources SET config_json = :config_json "
            "WHERE key = :key"
        ),
        {
            "key": "bazhou_gov",
            "config_json": json.dumps(_NEW_CONFIG, ensure_ascii=False),
        },
    )


def downgrade() -> None:
    # Keep the corrected source configuration on downgrade; restoring the old
    # homepage-wide collector would reintroduce navigation false positives.
    pass
