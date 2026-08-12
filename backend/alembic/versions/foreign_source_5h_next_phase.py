"""Add explicit manual foreign collection action permissions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "foreign_source_5h_next_phase"
down_revision: Union[str, None] = "foreign_source_5g_remediation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSIONS = [
    (
        "foreign:sources:collect",
        "Collect selected foreign RSS sources",
        "Run manual collection for an explicit approved foreign source list.",
    ),
    (
        "foreign:sources:collect_all",
        "Collect all foreign sources",
        "Run manual collection for every enabled foreign source in the approved scope.",
    ),
]


def _install_permissions(bind) -> None:
    for code, name, description in PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, 'foreign', :action, 'Foreign sources', :description, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code,
                "name": name,
                "action": code.rsplit(":", 1)[-1],
                "description": description,
            },
        )
    bind.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r CROSS JOIN permissions p
            WHERE (r.code = 'admin' OR r.name = 'admin')
              AND p.code IN :codes
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": [item[0] for item in PERMISSIONS]},
    )


def upgrade() -> None:
    _install_permissions(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    codes = [item[0] for item in PERMISSIONS]
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "(SELECT id FROM permissions WHERE code IN :codes)"
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": codes},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": codes},
    )
