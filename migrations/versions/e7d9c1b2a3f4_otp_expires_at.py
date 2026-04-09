"""otp expires at for auth codes

Revision ID: e7d9c1b2a3f4
Revises: b7831c038355
Create Date: 2026-04-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7d9c1b2a3f4'
down_revision = 'b7831c038355'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('otp_expires_at', sa.DateTime(), nullable=True))

    op.execute(sa.text(
        'UPDATE "user" '
        'SET otp_expires_at = NOW() + INTERVAL \'90 seconds\' '
        'WHERE otp_code IS NOT NULL AND is_verified = FALSE'
    ))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('otp_expires_at')