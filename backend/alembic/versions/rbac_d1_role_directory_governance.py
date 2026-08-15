"""Phase Security-RBAC-Redesign-D1：权限目录与角色分配治理（数据层，零 Enforcement 改动）。

仅修改 Role / Permission / role_permissions 数据：
- 新增正式角色 system_admin / operator（is_system=true，不持 *）。
- 修复 foreign:* 组合权限无人持有：foreign:read->analyst，foreign:data:manage->operator+system_admin。
- analyst 补齐 keywords:write / foreign:ai:review:read / foreign:ai:batch:read / foreign:ai:batch:cancel / foreign:read；
  收紧移除不应持有的 permissions:read 与 sources:write（幽灵权限）。
- 清理游离角色 111（无用户/附加角色引用时）。

不修改任何 API Enforcement、require_permission、require_admin、expand_permissions、
COMPOSITE_PERMISSIONS、Service 层、前端、role_permissions schema，也不实现 Capability，
不新增 collector:run。幂等、可重复执行；downgrade 精确回滚至 BEFORE。
"""
from alembic import op
from sqlalchemy.orm import Session

from app.core.rbac_d1 import apply_d1_role_fixes, revert_d1_role_fixes

# revision identifiers, used by Alembic.
revision = "rbac_d1_role_gov_v1"
down_revision = "review_decision_complete_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # op.get_bind() 已处于 Alembic 事务内；只 flush，由 Alembic 在上下文退出时统一提交，
    # 出现异常时由 Alembic 自动回滚（保证 D1 生产变更可整体回退）。
    bind = op.get_bind()
    session = Session(bind=bind)
    apply_d1_role_fixes(session)


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    revert_d1_role_fixes(session)
