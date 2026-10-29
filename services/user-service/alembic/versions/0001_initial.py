"""initial schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("skills", pg.ARRAY(sa.Text), nullable=False),
        sa.Column("location", sa.String(255)),
        sa.Column("min_salary", sa.Integer),
        sa.Column("currency", sa.String(8)),
        sa.Column("telegram_chat_id", sa.String(64)),
        sa.Column("active", sa.Boolean, nullable=False),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.create_table(
        "outbox",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("topic", sa.String(64), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("payload", pg.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_outbox_published_at", "outbox", ["published_at"])


def downgrade():
    op.drop_table("outbox")
    op.drop_table("subscriptions")
    op.drop_table("users")
