"""advert and feedback images

Revision ID: ad7c3e6b91a2
Revises: f1b0c9d4e6a2
Create Date: 2026-04-12 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ad7c3e6b91a2'
down_revision = 'f1b0c9d4e6a2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('advert', sa.Column('image_file', sa.String(length=255), nullable=True))
    op.add_column('feedback', sa.Column('image_file', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('feedback', 'image_file')
    op.drop_column('advert', 'image_file')