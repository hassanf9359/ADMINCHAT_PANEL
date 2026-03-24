"""Add installed_plugins and plugin_secrets tables for plugin system

Revision ID: 008_add_plugin_tables
Revises: 007_add_movie_requests
Create Date: 2026-03-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "008_add_plugin_tables"
down_revision: Union[str, None] = "007_add_movie_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Installed plugins
    op.create_table(
        "installed_plugins",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("plugin_id", sa.String(50), unique=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("previous_version", sa.String(20), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            server_default="installed",
            nullable=False,
        ),
        sa.Column("manifest", JSONB(), nullable=False),
        sa.Column("config", JSONB(), server_default="{}", nullable=True),
        sa.Column("license_key", sa.String(200), nullable=True),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_installed_plugins_plugin_id", "installed_plugins", ["plugin_id"])
    op.create_index("ix_installed_plugins_status", "installed_plugins", ["status"])

    # Plugin secrets
    op.create_table(
        "plugin_secrets",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("plugin_id", sa.String(50), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("plugin_id", "key", name="uq_plugin_secret"),
    )
    op.create_index("ix_plugin_secrets_plugin_id", "plugin_secrets", ["plugin_id"])


def downgrade() -> None:
    op.drop_table("plugin_secrets")
    op.drop_table("installed_plugins")
