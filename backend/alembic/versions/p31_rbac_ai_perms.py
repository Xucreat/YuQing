"""p31_rbac_ai_perms: 新增 AI 权限组（Phase RBAC 权限收口）

Revises: p30_event_actions_deprecated
Create Date: 2026-07-31

变更（纯数据，幂等，无 schema 变更）：
  - 新增 3 个权限码（group='AI能力'）：
      * ai:search   AI 检索（Web Search / AI Search / Anspire）
      * ai:analyze  AI 研判（单条舆情触发 DeepSeek 分析）
      * ai:manage   AI 配置管理（预留，暂无接口挂载）
  - 授予 analyst 角色 ai:search + ai:analyze（保持其现有 AI 使用能力不回归）。
  - admin 为超级管理员（is_superuser → ["*"]），无需显式授予；同时按既有惯例
    把 3 项 AI 权限写入 admin 角色，便于角色权限页可视化。
  - viewer 不授予任何 AI 权限（本次收口目标：观察者不可使用 AI 能力）。

安全边界：
  - 不新建/删除任何表，不修改任何业务数据模型。
  - 不撤销任何已有授权，管理员判定逻辑（is_superuser_user）完全不变。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p31_rbac_ai_perms"
down_revision: Union[str, None] = "p30_event_actions_deprecated"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_AI_PERMISSIONS = [
    # code, name, resource, action, group, description
    ("ai:search", "AI检索", "ai", "search", "AI能力", "使用 AI 检索（Web/AI/Anspire）并保存线索"),
    ("ai:analyze", "AI研判", "ai", "analyze", "AI能力", "对单条舆情触发 AI 研判分析"),
    ("ai:manage", "AI配置管理", "ai", "manage", "AI能力", "管理 AI 服务配置（预留）"),
]

# 角色 → 授予的 AI 权限
_GRANTS = {
    "admin": ["ai:search", "ai:analyze", "ai:manage"],
    "analyst": ["ai:search", "ai:analyze"],
}


def upgrade() -> None:
    bind = op.get_bind()

    # ---------- 1. 写入权限目录（幂等） ----------
    for code, name, resource, action, group, desc in _AI_PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, :resource, :action, :group, :desc, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code, "name": name, "resource": resource,
                "action": action, "group": group, "desc": desc,
            },
        )

    # ---------- 2. 授予既有角色（幂等，不撤销任何已有授权） ----------
    for role_code, codes in _GRANTS.items():
        for code in codes:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT r.id, p.id
                    FROM roles r, permissions p
                    WHERE (r.code = :role_code OR r.name = :role_code)
                      AND p.code = :code
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                    """
                ),
                {"role_code": role_code, "code": code},
            )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (SELECT id FROM permissions WHERE code LIKE 'ai:%')
            """
        )
    )
    bind.execute(sa.text("DELETE FROM permissions WHERE code LIKE 'ai:%'"))
