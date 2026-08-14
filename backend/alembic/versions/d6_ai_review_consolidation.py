"""D6 — Safe Permission Consolidation: AI review read/complete.

Phase Security-RBAC-Redesign-D6 (Safe Permission Consolidation Implementation).

Scope (per D6 spec, ONLY the two D5 MUST-CONSOLIDATE groups):
  * domestic:ai:review:read    + foreign:ai:review:read    -> ai:review:read
  * domestic:ai:review:complete + foreign:ai:review:complete -> ai:review:complete

Security guarantee (verified via preflight SELECT on prod 127.0.0.1:5432/opinion_db):
  * Old role sets (BEFORE):
      domestic:ai:review:read     -> admin, analyst, viewer
      foreign:ai:review:read      -> analyst, viewer
      domestic:ai:review:complete -> admin, analyst, viewer
      foreign:ai:review:complete  -> admin, analyst, viewer
  * Union (AFTER target):
      ai:review:read     -> admin, analyst, viewer
      ai:review:complete -> admin, analyst, viewer
  => For every role the effective authorization is IDENTICAL (no new capability).
  => analyst/operator/viewer/system_admin do NOT gain any Foreign capability.

Out of scope (explicitly NOT touched by D6):
  * sources:write / foreign:sources:write (RECOMMENDED, deferred)
  * all D5 KEEP-SEPARATE groups (BLOCKED-BY-SCOPE-DIFFERENCE)
  * all D5 DEFER groups incl. foreign:analysis / foreign:alerts:manage /
    foreign:alerts:false_positive / foreign:ai:review:reject (Foreign high-risk)
  * No schema change. No new role. No role semantic change. No require_permission change.
  * No Capability / ABAC / Scope engine.

Reversibility: downgrade precisely restores the 4 old permission rows AND their
exact BEFORE role_permissions (role sets are hardcoded from the verified prod
preflight; the merge is a union, so the split-back mapping is deterministic).

Note on composite maps: the `ai:analyze` and `foreign:analysis` composites in
app/core/permissions.py reference the two deleted leaves; they are updated in
that file (code change) to point at the unified perms. `foreign:analysis`
remains an orphan (0 holders) and its authorization boundary is unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6_ai_review_consolidation"
down_revision: Union[str, None] = "p34_foreign_event_status_unify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# New unified permissions
# ---------------------------------------------------------------------------
NEW_PERMISSIONS = [
    (
        "ai:review:read",
        "查看 AI 人工复核",
        "ai",
        "review_read",
        "AI 研判",
        "查看 AI 人工复核（国内/外网统一）",
    ),
    (
        "ai:review:complete",
        "完成 AI 人工复核",
        "ai",
        "review_complete",
        "AI 研判",
        "关闭/完成一条 AI 人工复核（国内/外网统一，不自动创建事件或预警）",
    ),
]

# (old_a, old_b) -> new unified code
MERGE_PAIRS = [
    ("domestic:ai:review:read", "foreign:ai:review:read", "ai:review:read"),
    ("domestic:ai:review:complete", "foreign:ai:review:complete", "ai:review:complete"),
]

# 4 old permissions to delete (code, name, resource, action, group, description)
# — exact prod metadata captured during preflight; used only by downgrade.
OLD_PERMISSIONS = [
    (
        "domestic:ai:review:read",
        "查看国内 AI 人工复核",
        "domestic",
        "review_read",
        "国内 AI",
        "查看国内 AI 人工复核",
    ),
    (
        "domestic:ai:review:complete",
        "完成国内 AI 人工复核",
        "domestic",
        "review_complete",
        "国内 AI",
        "关闭/完成一条国内 AI 人工复核（不自动创建事件或预警）",
    ),
    (
        "foreign:ai:review:read",
        "查看外网 AI 人工复核",
        "foreign",
        "review_read",
        "外网 AI",
        "查看外网 AI 人工复核",
    ),
    (
        "foreign:ai:review:complete",
        "完成外网 AI 人工复核",
        "foreign",
        "review_complete",
        "外网 AI",
        "关闭/完成一条外网 AI 人工复核（不自动创建事件或预警）",
    ),
]

# Exact BEFORE role sets (role.name) — verified via prod preflight SELECT.
OLD_ROLE_SETS = {
    "domestic:ai:review:read": ["admin", "analyst", "viewer"],
    "foreign:ai:review:read": ["analyst", "viewer"],
    "domestic:ai:review:complete": ["admin", "analyst", "viewer"],
    "foreign:ai:review:complete": ["admin", "analyst", "viewer"],
}

OLD_CODES = [p[0] for p in OLD_PERMISSIONS]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _install_new_permissions(bind) -> None:
    for code, name, resource, action, group, description in NEW_PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions
                    (code, name, resource, action, "group", description, created_at)
                VALUES
                    (:code, :name, :resource, :action, :group, :description, :created_at)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code,
                "name": name,
                "resource": resource,
                "action": action,
                "group": group,
                "description": description,
                "created_at": _now(),
            },
        )


def _migrate_role_permissions(bind) -> None:
    """Grant each new unified perm to the UNION of roles holding either old leaf."""
    for old_a, old_b, new_code in MERGE_PAIRS:
        bind.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, np.id
                FROM roles r
                JOIN permissions np ON np.code = :new_code
                WHERE r.id IN (
                    SELECT rp.role_id
                    FROM role_permissions rp
                    JOIN permissions p ON p.id = rp.permission_id
                    WHERE p.code = :old_a OR p.code = :old_b
                )
                ON CONFLICT (role_id, permission_id) DO NOTHING
                """
            ),
            {"new_code": new_code, "old_a": old_a, "old_b": old_b},
        )


def _delete_old_permissions(bind) -> None:
    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE code IN :codes
            )
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": OLD_CODES},
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN :codes
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": OLD_CODES},
    )


def _restore_old_permissions(bind) -> None:
    for code, name, resource, action, group, description in OLD_PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions
                    (code, name, resource, action, "group", description, created_at)
                VALUES
                    (:code, :name, :resource, :action, :group, :description, :created_at)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code,
                "name": name,
                "resource": resource,
                "action": action,
                "group": group,
                "description": description,
                "created_at": _now(),
            },
        )
        roles = OLD_ROLE_SETS[code]
        bind.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r
                JOIN permissions p ON p.code = :code
                WHERE r.name IN :roles
                ON CONFLICT (role_id, permission_id) DO NOTHING
                """
            ).bindparams(sa.bindparam("roles", expanding=True)),
            {"code": code, "roles": roles},
        )


def _delete_new_permissions(bind) -> None:
    new_codes = [p[0] for p in NEW_PERMISSIONS]
    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE code IN :codes
            )
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": new_codes},
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN :codes
            """
        ).bindparams(sa.bindparam("codes", expanding=True)),
        {"codes": new_codes},
    )


def upgrade() -> None:
    bind = op.get_bind()
    _install_new_permissions(bind)
    _migrate_role_permissions(bind)
    _delete_old_permissions(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _restore_old_permissions(bind)
    _delete_new_permissions(bind)
