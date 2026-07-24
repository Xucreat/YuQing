"""p12_rbac_roleperms: 增量补齐三角色权限（纯数据，零 DDL）

RBAC 权限收口（最小改动，不新增角色 / 不改动表结构 / 不引入新权限码）：

  - analyst  + sources:read       （查看数据源状态/采集日志，不管理）
  - viewer   + alerts:read        （领导查看风险预警）
  - viewer   + propagation:read   （领导查看传播路径）

设计要点：
  - collectors:read / collectors:write 权限码保留在目录中（reserved/unused），
    不删除、不新增 trigger/manage 权限码；当前无运行时「管理」接口需要保护。
  - 本迁移仅 INSERT 关联行，使用 NOT EXISTS 幂等判断，重复执行安全（已存在的
    绑定不会重复插入，也不 DELETE 任何既有绑定，避免覆盖人工调整过的角色权限）。
  - downgrade 仅按 (role, permission) 精确删除本次新增的 3 行，不影响其他绑定。

数据核验前置（已在执行前完成）：
  - 生产库 opinion_db 身份 VERIFIED（opinions>=100，alembic head=p11_phase2b2）。
  - 三角色权限与种子默认值一致，无人工作过，可安全增量执行。
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "p12_rbac_roleperms"
down_revision: Union[str, None] = "p11_phase2b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (角色名, 权限码) — 仅补齐缺失项，绝不覆盖/删除既有绑定
_BINDINGS = [
    ("analyst", "sources:read"),
    ("viewer", "alerts:read"),
    ("viewer", "propagation:read"),
]


def _insert(bind) -> None:
    for role_name, perm_code in _BINDINGS:
        bind.execute(
            text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r, permissions p
                WHERE r.name = :role AND p.code = :perm
                  AND NOT EXISTS (
                    SELECT 1 FROM role_permissions rp
                    WHERE rp.role_id = r.id AND rp.permission_id = p.id
                  )
                """
            ),
            {"role": role_name, "perm": perm_code},
        )


def _delete(bind) -> None:
    for role_name, perm_code in _BINDINGS:
        bind.execute(
            text(
                """
                DELETE FROM role_permissions rp
                USING roles r, permissions p
                WHERE rp.role_id = r.id
                  AND rp.permission_id = p.id
                  AND r.name = :role
                  AND p.code = :perm
                """
            ),
            {"role": role_name, "perm": perm_code},
        )


def upgrade() -> None:
    _insert(op.get_bind())


def downgrade() -> None:
    _delete(op.get_bind())
