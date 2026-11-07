"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-11-07 10:25:37.954535
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('ad_banners',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('image_url', sa.String(length=500), nullable=False),
    sa.Column('link', sa.String(length=500), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ad_banners'))
    )
    op.create_table('disciplines',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_disciplines'))
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('group', sa.String(length=50), nullable=True),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('labs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('discipline_id', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('expected_minutes', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['discipline_id'], ['disciplines.id'], name=op.f('fk_labs_discipline_id_disciplines'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_labs')),
    sa.UniqueConstraint('discipline_id', 'number', name=op.f('uq_labs_discipline_id'))
    )
    op.create_table('queues',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('discipline_id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('starts_at', sa.Time(), nullable=False),
    sa.Column('ends_at', sa.Time(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('aging_k', sa.Double(), nullable=False),
    sa.ForeignKeyConstraint(['discipline_id'], ['disciplines.id'], name=op.f('fk_queues_discipline_id_disciplines'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], name=op.f('fk_queues_teacher_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_queues'))
    )
    op.create_table('queue_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('queue_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('called_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('pinned_position', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['queue_id'], ['queues.id'], name=op.f('fk_queue_entries_queue_id_queues'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], name=op.f('fk_queue_entries_student_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_queue_entries'))
    )
    op.create_index('ix_queue_entries_queue_id_status', 'queue_entries', ['queue_id', 'status'], unique=False)
    op.create_index('uq_queue_entries_active_student', 'queue_entries', ['queue_id', 'student_id'], unique=True, postgresql_where=sa.text("status IN ('waiting', 'called', 'testing', 'reviewing')"), sqlite_where=sa.text("status IN ('waiting', 'called', 'testing', 'reviewing')"))
    op.create_table('tests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lab_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('time_limit_min', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], name=op.f('fk_tests_lab_id_labs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tests'))
    )
    op.create_table('entry_labs',
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('lab_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['entry_id'], ['queue_entries.id'], name=op.f('fk_entry_labs_entry_id_queue_entries'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lab_id'], ['labs.id'], name=op.f('fk_entry_labs_lab_id_labs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('entry_id', 'lab_id', name=op.f('pk_entry_labs'))
    )
    op.create_table('questions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('options', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('correct', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['test_id'], ['tests.id'], name=op.f('fk_questions_test_id_tests'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_questions'))
    )
    op.create_table('test_attempts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('test_id', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('score', sa.Double(), nullable=True),
    sa.ForeignKeyConstraint(['entry_id'], ['queue_entries.id'], name=op.f('fk_test_attempts_entry_id_queue_entries'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['test_id'], ['tests.id'], name=op.f('fk_test_attempts_test_id_tests'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_test_attempts'))
    )
    op.create_table('answers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('attempt_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('value', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['attempt_id'], ['test_attempts.id'], name=op.f('fk_answers_attempt_id_test_attempts'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], name=op.f('fk_answers_question_id_questions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_answers')),
    sa.UniqueConstraint('attempt_id', 'question_id', name=op.f('uq_answers_attempt_id'))
    )


def downgrade() -> None:
    op.drop_table('answers')
    op.drop_table('test_attempts')
    op.drop_table('questions')
    op.drop_table('entry_labs')
    op.drop_table('tests')
    op.drop_index('uq_queue_entries_active_student', table_name='queue_entries', postgresql_where=sa.text("status IN ('waiting', 'called', 'testing', 'reviewing')"), sqlite_where=sa.text("status IN ('waiting', 'called', 'testing', 'reviewing')"))
    op.drop_index('ix_queue_entries_queue_id_status', table_name='queue_entries')
    op.drop_table('queue_entries')
    op.drop_table('queues')
    op.drop_table('labs')
    op.drop_table('users')
    op.drop_table('disciplines')
    op.drop_table('ad_banners')
