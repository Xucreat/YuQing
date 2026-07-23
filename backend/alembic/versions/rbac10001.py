"""rbac10001: RBAC 规范化 + 审计日志（Phase RBAC-1）

Revises: kwlex01
Create Date: 2026-07-23

Schema:
  - users:  + is_superuser, display_name, email, last_login_ip, updated_at
  - roles:  + code, description, is_system, is_enabled, updated_at; 移除 permissions(JSONB)
  - 新表:  permissions, role_permissions, user_roles,
           user_login_logs, user_operation_logs

Data（幂等，仅对已有数据）:
  - 把 roles.permissions(JSONB) 迁移进 role_permissions
  - 为系统角色设置 code / is_system
  - 给 admin 角色用户置 is_superuser=true
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "rbac10001"
down_revision: Union[str, None] = "kwlex01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # ---------- users 扩展 ----------
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("display_name", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("last_login_ip", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # ---------- roles 扩展（先加列，稍后删 permissions） ----------
    op.add_column("roles", sa.Column("code", sa.String(32), nullable=False, server_default=""))
    op.add_column("roles", sa.Column("description", sa.String(255), nullable=True))
    op.add_column("roles", sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("roles", sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("roles", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")))
    op.create_unique_constraint("uq_roles_code", "roles", ["code"])

    # ---------- permissions 目录表 ----------
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("resource", sa.String(32), nullable=False, server_default=""),
        sa.Column("action", sa.String(32), nullable=False, server_default=""),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("group", sa.String(32), nullable=False, server_default="其他"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])

    # ---------- role_permissions 关联表 ----------
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )

    # ---------- user_roles 关联表 ----------
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )

    # ---------- 登录日志 ----------
    op.create_table(
        "user_login_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("login_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_login_logs_user_id", "user_login_logs", ["user_id"])
    op.create_index("ix_user_login_logs_username", "user_login_logs", ["username"])
    op.create_index("ix_user_login_logs_status", "user_login_logs", ["status"])

    # ---------- 操作审计日志 ----------
    op.create_table(
        "user_operation_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("operator_username_snapshot", sa.String(64), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("request_method", sa.String(8), nullable=True),
        sa.Column("request_path", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("result", sa.String(16), nullable=False, server_default="success"),
        sa.Column("error_message", sa.String(512), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_operation_logs_operator", "user_operation_logs", ["operator_user_id"])
    op.create_index("ix_user_operation_logs_target", "user_operation_logs", ["target_user_id"])
    op.create_index("ix_user_operation_logs_action", "user_operation_logs", ["action"])

    # ---------- 数据迁移（幂等） ----------
    _seed_permissions(bind)
    _migrate_role_permissions(bind)
    _flag_system_roles(bind)
    _flag_superusers(bind)

    # ---------- 最后移除旧 JSONB 权限列 ----------
    op.drop_column("roles", "permissions")


def downgrade() -> None:
    op.add_column("roles", sa.Column("permissions", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"))
    op.drop_table("user_operation_logs")
    op.drop_table("user_login_logs")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_index("ix_permissions_code", "permissions")
    op.drop_table("permissions")
    op.drop_constraint("uq_roles_code", "roles", type_="unique")
    op.drop_column("roles", "updated_at")
    op.drop_column("roles", "is_enabled")
    op.drop_column("roles", "is_system")
    op.drop_column("roles", "description")
    op.drop_column("roles", "code")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "last_login_ip")
    op.drop_column("users", "email")
    op.drop_column("users", "display_name")
    op.drop_column("users", "is_superuser")


# ---- 权限目录（与 init_db.py 保持一致） ----
_PERMISSIONS = [
    # code, name, resource, action, group, description
    ("users:read", "查看用户", "users", "read", "用户管理", "查看用户列表与详情"),
    ("users:write", "管理用户", "users", "write", "用户管理", "创建/编辑用户"),
    ("users:activate", "启用/停用用户", "users", "activate", "用户管理", "启用或停用用户"),
    ("roles:read", "查看角色", "roles", "read", "角色管理", "查看角色列表"),
    ("roles:write", "管理角色", "roles", "write", "角色管理", "创建/编辑/分配权限"),
    ("roles:delete", "删除角色", "roles", "delete", "角色管理", "删除非系统角色"),
    ("permissions:read", "查看权限", "permissions", "read", "权限管理", "查看权限目录"),
    ("keywords:read", "查看关键词", "keywords", "read", "关键词管理", "查看监测/敏感词"),
    ("keywords:write", "管理关键词", "keywords", "write", "关键词管理", "增删改关键词"),
    ("keywords:delete", "删除关键词", "keywords", "delete", "关键词管理", "删除关键词"),
    ("opinions:read", "查看舆情", "opinions", "read", "舆情管理", "查看舆情列表/详情"),
    ("opinions:write", "管理舆情", "opinions", "write", "舆情管理", "删除/编辑舆情"),
    ("events:read", "查看事件", "events", "read", "事件管理", "查看事件中心"),
    ("events:write", "管理事件", "events", "write", "事件管理", "聚合/编辑事件"),
    ("alerts:read", "查看预警", "alerts", "read", "预警管理", "查看预警规则与记录"),
    ("alerts:write", "管理预警", "alerts", "write", "预警管理", "配置/评估预警"),
    ("collectors:read", "查看采集", "collectors", "read", "采集管理", "查看采集任务"),
    ("collectors:write", "管理采集", "collectors", "write", "采集管理", "启停采集任务"),
    ("sources:read", "查看数据源", "sources", "read", "数据源", "查看数据源"),
    ("sources:write", "管理数据源", "sources", "write", "数据源", "管理数据源"),
    ("propagation:read", "查看传播", "propagation", "read", "传播溯源", "查看传播路径"),
    ("dashboard:read", "查看驾驶舱", "dashboard", "read", "驾驶舱", "查看数据总览"),
    ("reports:read", "查看报告", "reports", "read", "报告", "查看分析报告"),
    ("reports:write", "导出报告", "reports", "write", "报告", "导出PDF报告"),
    ("audit_logs:read", "查看操作日志", "audit_logs", "read", "审计", "查看操作审计日志"),
    ("login_logs:read", "查看登录日志", "login_logs", "read", "审计", "查看登录日志"),
]


def _seed_permissions(bind) -> None:
    for code, name, resource, action, group, desc in _PERMISSIONS:
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


def _migrate_role_permissions(bind) -> None:
    """把 roles.permissions(JSONB) 迁移到 role_permissions（幂等）。"""
    rows = bind.execute(
        sa.text("SELECT id, permissions FROM roles WHERE permissions IS NOT NULL")
    ).fetchall()
    for role_id, perms in rows:
        if not perms:
            continue
        # 已迁移过则跳过
        cnt = bind.execute(
            sa.text("SELECT count(*) FROM role_permissions WHERE role_id = :rid"),
            {"rid": role_id},
        ).scalar()
        if cnt and cnt > 0:
            continue
        for code in perms:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO role_permissions (role_id, permission_id)
                    SELECT :rid, p.id FROM permissions p WHERE p.code = :code
                    ON CONFLICT (role_id, permission_id) DO NOTHING
                    """
                ),
                {"rid": role_id, "code": code},
            )


def _flag_system_roles(bind) -> None:
    for name, code in [("admin", "admin"), ("analyst", "analyst"), ("viewer", "viewer")]:
        bind.execute(
            sa.text(
                """
                UPDATE roles
                SET code = :code, is_system = true, is_enabled = true, updated_at = now()
                WHERE name = :name AND (code = '' OR code IS NULL)
                """
            ),
            {"code": code, "name": name},
        )


def _flag_superusers(bind) -> None:
    bind.execute(
        sa.text("UPDATE users SET is_superuser = true WHERE role = 'admin'")
    )
