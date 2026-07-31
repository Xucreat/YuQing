"""sec3b_perm_semantic: RBAC 权限语义收口（Phase Security-3-B）

Revises: p31_rbac_ai_perms
Create Date: 2026-07-31

Changes:
  1. Delete 5 orphan permissions (permissions 表无 is_enabled 列，直接删除行):
     - keywords:delete (id=10)
     - reports:write (id=24)
     - collectors:read (id=17)
     - collectors:write (id=18)
     - dashboard:read (id=22)
     注意: 先删除 role_permissions 中对这些权限的引用，再删 permissions 行。

  2. Update 3 permission descriptions:
     - opinions:write (id=12): "删除/编辑舆情" → "编辑舆情"
     - sources:read (id=19): "查看数据源" → "查看数据源状态（管理操作仅管理员）"
     - sources:write (id=20): "管理数据源" → "管理员管理数据源"

  3. Remove analyst(role_id=2) → sources:write(permission_id=20) grant
     (此授权码前端/后端均不引用，对 analyst 无实际作用)

Rollback:
  - Re-insert 5 deleted permissions with original data
  - Restore original descriptions
  - Re-add analyst → sources:write grant
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'sec3b_perm_semantic'
down_revision = 'p31_rbac_ai_perms'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply permission semantic corrections."""

    # ── 1a. Remove role_permissions references to orphan perms ──
    # 这些权限在 role_permissions 中的引用必须先清除（FK 约束）
    # analyst→dashboard:read(id=22), analyst→reports:write(id=24),
    # viewer→dashboard:read(id=22) 已在 role_permissions 中
    op.execute(
        "DELETE FROM role_permissions "
        "WHERE permission_id IN (10, 17, 18, 22, 24)"
    )

    # ── 1b. Delete 5 orphan permission rows ──
    # keywords:delete(10), collectors:read(17), collectors:write(18),
    # dashboard:read(22), reports:write(24)
    op.execute(
        "DELETE FROM permissions "
        "WHERE id IN (10, 17, 18, 22, 24)"
    )

    # ── 2. Update descriptions ──
    # opinions:write: "删除/编辑舆情" → "编辑舆情"
    # (删除独占 ADMIN，此码仅涵盖编辑)
    op.execute(
        "UPDATE permissions SET description = '编辑舆情' "
        "WHERE code = 'opinions:write'"
    )
    # sources:read: 添加管理限制说明
    op.execute(
        "UPDATE permissions SET description = '查看数据源状态（管理操作仅管理员）' "
        "WHERE code = 'sources:read'"
    )
    # sources:write: 标记为管理员专属
    op.execute(
        "UPDATE permissions SET description = '管理员管理数据源' "
        "WHERE code = 'sources:write'"
    )

    # ── 3. Remove analyst → sources:write grant ──
    # analyst(role_id=2) 不应持有 sources:write——前端锁在 isSuperuser，后端写全 ADMIN
    op.execute(
        "DELETE FROM role_permissions "
        "WHERE role_id = 2 AND permission_id = 20"
    )


def downgrade() -> None:
    """Rollback all changes to pre-3-B state."""

    # ── 1. Re-insert 5 deleted permissions ──
    # 恢复原始数据（id, code, name, resource, action, description, group）
    op.execute(
        "INSERT INTO permissions (id, code, name, resource, action, description, \"group\") "
        "VALUES "
        "(10, 'keywords:delete', '删除关键词', 'keywords', 'delete', '删除关键词', '关键词管理'), "
        "(17, 'collectors:read', '查看采集', 'collectors', 'read', '查看采集任务', '采集管理'), "
        "(18, 'collectors:write', '管理采集', 'collectors', 'write', '启停采集任务', '采集管理'), "
        "(22, 'dashboard:read', '查看驾驶舱', 'dashboard', 'read', '查看数据总览', '驾驶舱'), "
        "(24, 'reports:write', '导出报告', 'reports', 'write', '导出PDF报告', '报告') "
        "ON CONFLICT (id) DO NOTHING"
    )

    # ── 1b. Restore role_permissions references ──
    # analyst→dashboard:read(22), analyst→reports:write(24),
    # viewer→dashboard:read(22)
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) VALUES "
        "(2, 22), (2, 24), (3, 22) "
        "ON CONFLICT DO NOTHING"
    )

    # ── 2. Restore original descriptions ──
    op.execute(
        "UPDATE permissions SET description = '删除/编辑舆情' "
        "WHERE code = 'opinions:write'"
    )
    op.execute(
        "UPDATE permissions SET description = '查看数据源' "
        "WHERE code = 'sources:read'"
    )
    op.execute(
        "UPDATE permissions SET description = '管理数据源' "
        "WHERE code = 'sources:write'"
    )

    # ── 3. Restore analyst → sources:write grant ──
    op.execute(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "VALUES (2, 20) "
        "ON CONFLICT DO NOTHING"
    )
