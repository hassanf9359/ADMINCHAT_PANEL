"""Add bot_groups, faq_groups, faq_categories tables and faq_rules.category_id

Revision ID: 001_bot_faq_groups
Revises:
Create Date: 2026-03-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '001_bot_faq_groups'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- bot_groups ---
    op.create_table(
        'bot_groups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # --- bot_group_members ---
    op.create_table(
        'bot_group_members',
        sa.Column('bot_group_id', sa.Integer(), sa.ForeignKey('bot_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bot_id', sa.Integer(), sa.ForeignKey('bots.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('bot_group_id', 'bot_id'),
        sa.UniqueConstraint('bot_id', name='uq_bot_group_members_bot_id'),
    )

    # --- faq_groups ---
    op.create_table(
        'faq_groups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('bot_group_id', sa.Integer(), sa.ForeignKey('bot_groups.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # --- faq_categories ---
    op.create_table(
        'faq_categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('faq_group_id', sa.Integer(), sa.ForeignKey('faq_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bot_group_id', sa.Integer(), sa.ForeignKey('bot_groups.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # --- faq_rules.category_id ---
    op.add_column(
        'faq_rules',
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('faq_categories.id', ondelete='SET NULL'), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('faq_rules', 'category_id')
    op.drop_table('faq_categories')
    op.drop_table('faq_groups')
    op.drop_table('bot_group_members')
    op.drop_table('bot_groups')
