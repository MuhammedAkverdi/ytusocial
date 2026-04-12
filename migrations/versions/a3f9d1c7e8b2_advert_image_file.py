"""add image file to advert

Revision ID: a3f9d1c7e8b2
Revises: f1b0c9d4e6a2
Create Date: 2026-04-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3f9d1c7e8b2'
down_revision = 'f1b0c9d4e6a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('advert', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_file', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('advert', schema=None) as batch_op:
        batch_op.drop_column('image_file')