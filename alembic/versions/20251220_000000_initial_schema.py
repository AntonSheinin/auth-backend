"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-12-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tokens table
    op.create_table(
        'tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('max_sessions', sa.Integer(), nullable=False),
        sa.Column('valid_from', sa.DateTime(), nullable=False),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('allowed_ips', sa.Text(), nullable=True),
        sa.Column('allowed_streams', sa.Text(), nullable=True),
        sa.Column('meta', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tokens_token', 'tokens', ['token'], unique=True)
    op.create_index('ix_tokens_user_id', 'tokens', ['user_id'], unique=False)
    op.create_index('ix_tokens_status', 'tokens', ['status'], unique=False)

    # Create active_sessions table
    op.create_table(
        'active_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('token_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('stream_name', sa.String(length=255), nullable=False),
        sa.Column('client_ip', sa.String(length=45), nullable=False),
        sa.Column('protocol', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('last_checked_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['token_id'], ['tokens.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_active_sessions_session_id', 'active_sessions', ['session_id'], unique=True)
    op.create_index('ix_active_sessions_user_id', 'active_sessions', ['user_id'], unique=False)
    op.create_index('ix_active_sessions_expires_at', 'active_sessions', ['expires_at'], unique=False)

    # Create access_logs table
    op.create_table(
        'access_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('stream_name', sa.String(length=255), nullable=True),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('protocol', sa.String(length=20), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_access_logs_timestamp', 'access_logs', ['timestamp'], unique=False)
    op.create_index('ix_access_logs_result', 'access_logs', ['result'], unique=False)


def downgrade() -> None:
    op.drop_table('access_logs')
    op.drop_table('active_sessions')
    op.drop_table('tokens')
