"""add unique constraint for likes

Revision ID: f1b0c9d4e6a2
Revises: e7d9c1b2a3f4
Create Date: 2026-04-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1b0c9d4e6a2'
down_revision = 'e7d9c1b2a3f4'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'postgresql':
        op.execute(
            """
            DELETE FROM likes a
            USING likes b
            WHERE a.user_id = b.user_id
              AND a.post_id = b.post_id
              AND a.ctid < b.ctid
            """
        )
    elif dialect_name == 'sqlite':
        op.execute(
            """
            DELETE FROM likes
            WHERE rowid NOT IN (
                SELECT MIN(rowid)
                FROM likes
                GROUP BY user_id, post_id
            )
            """
        )

    with op.batch_alter_table('likes', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_likes_user_post', ['user_id', 'post_id'])


def downgrade():
    with op.batch_alter_table('likes', schema=None) as batch_op:
        batch_op.drop_constraint('uq_likes_user_post', type_='unique')
