"""Add auth_method and oauth_data columns to ai_configs

Revision ID: 002_add_oauth
Revises: 001_bot_faq_groups
Create Date: 2026-03-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision: str = '002_add_oauth'
down_revision: Union[str, None] = '001_bot_faq_groups'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'ai_configs',
        sa.Column('auth_method', sa.String(30), nullable=False, server_default='api_key'),
    )
    op.add_column(
        'ai_configs',
        sa.Column('oauth_data', JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column('ai_configs', 'oauth_data')
    op.drop_column('ai_configs', 'auth_method')
