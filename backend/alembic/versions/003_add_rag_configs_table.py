"""Add rag_configs table and faq_rules.rag_config_id FK

Revision ID: 003_rag_configs
Revises: 002_add_oauth
Create Date: 2026-03-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision: str = '003_rag_configs'
down_revision: Union[str, None] = '002_add_oauth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create rag_configs table
    op.create_table(
        'rag_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('api_key', sa.String(500), nullable=False),
        sa.Column('dataset_id', sa.String(200), nullable=False),
        sa.Column('top_k', sa.Integer(), server_default='3', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # 2. Add rag_config_id FK to faq_rules
    op.add_column(
        'faq_rules',
        sa.Column('rag_config_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_faq_rules_rag_config_id',
        'faq_rules', 'rag_configs',
        ['rag_config_id'], ['id'],
        ondelete='SET NULL',
    )

    # 3. Migrate existing system_settings rag_config to new table
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT value FROM system_settings WHERE key = 'rag_config'")
    )
    row = result.fetchone()
    if row and row[0]:
        import json
        cfg = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        provider = cfg.get('provider', 'dify')
        base_url = cfg.get('dify_base_url', '')
        api_key = cfg.get('dify_api_key', '')
        dataset_id = cfg.get('dify_dataset_id', '')
        top_k = cfg.get('top_k', 3)

        if base_url and api_key and dataset_id:
            conn.execute(
                sa.text(
                    "INSERT INTO rag_configs (name, provider, base_url, api_key, dataset_id, top_k) "
                    "VALUES (:name, :provider, :base_url, :api_key, :dataset_id, :top_k)"
                ),
                {
                    'name': f'Dify ({provider})',
                    'provider': provider,
                    'base_url': base_url,
                    'api_key': api_key,
                    'dataset_id': dataset_id,
                    'top_k': top_k,
                },
            )

    # 4. Delete old system_settings record
    conn.execute(sa.text("DELETE FROM system_settings WHERE key = 'rag_config'"))


def downgrade() -> None:
    op.drop_constraint('fk_faq_rules_rag_config_id', 'faq_rules', type_='foreignkey')
    op.drop_column('faq_rules', 'rag_config_id')
    op.drop_table('rag_configs')
