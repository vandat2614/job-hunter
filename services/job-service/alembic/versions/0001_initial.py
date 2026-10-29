"""initial schema"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255)),
        sa.Column("salary_min", sa.Integer),
        sa.Column("salary_max", sa.Integer),
        sa.Column("salary_currency", sa.String(8)),
        sa.Column("skills", pg.ARRAY(sa.Text), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_jobs_dedup_key", "jobs", ["dedup_key"], unique=True)
    op.execute(
        "ALTER TABLE jobs ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('simple', coalesce(title,'') || ' ' || "
        "coalesce(company,'') || ' ' || coalesce(description,''))) STORED"
    )
    op.execute("CREATE INDEX ix_jobs_search ON jobs USING GIN (search_vector)")
    op.execute("CREATE INDEX ix_jobs_skills ON jobs USING GIN (skills)")

    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_job_id", sa.String(128), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.UniqueConstraint("source", "source_job_id"),
    )
    op.create_index("ix_job_sources_job_id", "job_sources", ["job_id"])

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
    op.drop_table("job_sources")
    op.drop_table("jobs")
