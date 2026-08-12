"""Add combined foreign permission catalog entries (four-category scheme).

只新增「四类组合权限」目录项（foreign:read / foreign:data:manage /
foreign:analysis / foreign:alerts:manage），不分配给任何角色，
因此不会扩大 analyst / viewer 的既有权限。

权限判定仍由 app.core.permissions.COMPOSITE_PERMISSIONS 在解析层展开为
旧细粒度权限，后端 require_permission 与前端 /me 缓存行为不变。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "foreign_combined_perms_v1"
down_revision: Union[str, None] = "kwctxzero0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSIONS = [
    (
        "foreign:read",
        "Read foreign (combined)",
        "查看外网舆情/风险/事件/预警/规则/关键词/数据源（组合权限）",
        "Foreign combined",
    ),
    (
        "foreign:data:manage",
        "Manage foreign data (combined)",
        "外网关键词维护、数据源增改与测试、手动与批量采集、采集配置查看（组合权限）",
        "Foreign combined",
    ),
    (
        "foreign:analysis",
        "Analyze foreign (combined)",
        "外网风险分析/批量/AI、事件确认合并拆分与状态变更、事件重建聚合、预警评估与 AI 准入（组合权限）",
        "Foreign combined",
    ),
    (
        "foreign:alerts:manage",
        "Manage foreign alerts (combined)",
        "外网预警规则查看/编辑/启用停用、预警确认/解决/抑制（组合权限）",
        "Foreign combined",
    ),
]


def _install(bind) -> None:
    for code, name, description, group in PERMISSIONS:
        bind.execute(
            sa.text(
                """
                INSERT INTO permissions (code, name, resource, action, "group", description, created_at)
                VALUES (:code, :name, 'foreign', :action, :group, :description, now())
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {
                "code": code,
                "name": name,
                "action": code.rsplit(":", 1)[-1],
                "group": group,
                "description": description,
            },
        )


def upgrade() -> None:
    _install(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True)
        ),
        {"codes": [item[0] for item in PERMISSIONS]},
    )
