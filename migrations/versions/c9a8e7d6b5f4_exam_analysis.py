"""exam analysis tables

Revision ID: c9a8e7d6b5f4
Revises: e7d9c1b2a3f4
Create Date: 2026-04-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c9a8e7d6b5f4'
down_revision = 'e7d9c1b2a3f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'exam_analysis',
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('question_count', sa.Integer(), nullable=False),
        sa.Column('disclaimer', sa.Text(), nullable=False, server_default=sa.text("'Bu sonuçlar kullanıcı oylarıyla oluşmaktadır, resmi cevap anahtarı değildir.'")),
        sa.Column('comments_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('code'),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id']),
    )

    op.create_table(
        'exam_attempt',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exam_id', sa.String(length=80), nullable=False),
        sa.Column('group', sa.String(length=1), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'exam_id', name='unique_exam_attempt'),
        sa.ForeignKeyConstraint(['exam_id'], ['exam_analysis.code']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )

    op.create_table(
        'exam_response',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exam_id', sa.String(length=80), nullable=False),
        sa.Column('group', sa.String(length=1), nullable=False),
        sa.Column('question_no', sa.Integer(), nullable=False),
        sa.Column('selected_option', sa.String(length=1), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'exam_id', 'question_no', name='unique_exam_response'),
        sa.ForeignKeyConstraint(['exam_id'], ['exam_analysis.code']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )
    op.create_index('ix_exam_response_exam_question', 'exam_response', ['exam_id', 'question_no'], unique=False)

    op.create_table(
        'exam_comment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('exam_id', sa.String(length=80), nullable=False),
        sa.Column('group', sa.String(length=1), nullable=False),
        sa.Column('question_no', sa.Integer(), nullable=False),
        sa.Column('body', sa.String(length=500), nullable=False),
        sa.Column('report_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['exam_id'], ['exam_analysis.code']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
    )
    op.create_index('ix_exam_comment_exam_question', 'exam_comment', ['exam_id', 'question_no'], unique=False)


def downgrade():
    op.drop_index('ix_exam_comment_exam_question', table_name='exam_comment')
    op.drop_table('exam_comment')

    op.drop_index('ix_exam_response_exam_question', table_name='exam_response')
    op.drop_table('exam_response')

    op.drop_table('exam_attempt')
    op.drop_table('exam_analysis')
