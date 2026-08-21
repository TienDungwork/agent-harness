from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.types import JSON, TypeDecorator


class CompatibleJSON(TypeDecorator):
    """JSONB on Postgres, JSON elsewhere (SQLite tests)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class CompatibleUUID(TypeDecorator):
    """UUID on Postgres, String elsewhere."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        return str(value) if dialect.name != 'postgresql' else value

    def process_result_value(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        return str(value)


class CompatibleStringArray(TypeDecorator):
    """TEXT[] on Postgres, JSON list elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(ARRAY(Text()))
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = 'users'

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    keycloak_sub: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    credit_account: Mapped[CreditAccount | None] = relationship(
        back_populates='user', uselist=False
    )
    conversations: Mapped[list[UserConversation]] = relationship(back_populates='user')


class CreditAccount(Base):
    __tablename__ = 'credit_accounts'

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal('100.0'))
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal('100.0')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User] = relationship(back_populates='credit_account')


class UsageLedger(Base):
    __tablename__ = 'usage_ledger'
    __table_args__ = (
        Index(
            'usage_ledger_run_idem_uidx',
            'user_id',
            'run_id',
            unique=True,
            postgresql_where=text("run_id IS NOT NULL AND usage_type <> 'refund'"),
            sqlite_where=text("run_id IS NOT NULL AND usage_type <> 'refund'"),
        ),
        Index('usage_ledger_user_created_idx', 'user_id', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='CASCADE'), index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    usage_type: Mapped[str] = mapped_column(String(64), default='llm_run')
    units: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal('0'))
    cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal('0'))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


# Keep table name user_conversations for Milestone 1/2 compatibility.
# Extra columns support conversation index without a separate rename migration.
class UserConversation(Base):
    __tablename__ = 'user_conversations'

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='CASCADE'), index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default='active')
    source: Mapped[str] = mapped_column(String(32), default='web')
    agent_profile: Mapped[str | None] = mapped_column(String(128), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        'metadata', CompatibleJSON(), default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates='conversations')


class ConversationTool(Base):
    __tablename__ = 'conversation_tools'
    __table_args__ = (
        UniqueConstraint(
            'conversation_id', 'tool_kind', 'tool_name', name='conversation_tools_uniq'
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey('user_conversations.conversation_id', ondelete='CASCADE'),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='CASCADE'), index=True
    )
    tool_kind: Mapped[str] = mapped_column(String(32))
    tool_name: Mapped[str] = mapped_column(String(255))
    tool_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(CompatibleJSON(), default=dict)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserMcpServer(Base):
    __tablename__ = 'user_mcp_servers'
    __table_args__ = (
        UniqueConstraint('user_id', 'name', name='user_mcp_servers_uniq'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='CASCADE'), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    transport: Mapped[str] = mapped_column(String(16), default='http')
    config: Mapped[dict] = mapped_column(CompatibleJSON(), default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class UserSettingsBlob(Base):
    __tablename__ = 'user_settings_blobs'

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[Any] = mapped_column(CompatibleJSON(), default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


# ---- Infra (table prefix infra_ — works on SQLite + Postgres) ----


class InfraServer(Base):
    __tablename__ = 'infra_servers'
    __table_args__ = (Index('infra_servers_hostname_idx', 'hostname'),)

    id: Mapped[str] = mapped_column(
        CompatibleUUID(), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(128), unique=True)
    hostname: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(128))
    auth_type: Mapped[str] = mapped_column(String(16), default='key')
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(CompatibleStringArray(), default=list)
    host_key_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    host_key_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    credential: Mapped[InfraServerCredential | None] = relationship(
        back_populates='server', uselist=False, cascade='all, delete-orphan'
    )


class InfraServerCredential(Base):
    __tablename__ = 'infra_server_credentials'

    server_id: Mapped[str] = mapped_column(
        CompatibleUUID(),
        ForeignKey('infra_servers.id', ondelete='CASCADE'),
        primary_key=True,
    )
    ciphertext: Mapped[str] = mapped_column(Text)
    key_id: Mapped[str] = mapped_column(String(64), default='default')
    passphrase_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    server: Mapped[InfraServer] = relationship(back_populates='credential')


class InfraServerAccessGrant(Base):
    __tablename__ = 'infra_server_access_grants'
    __table_args__ = (
        UniqueConstraint('server_id', 'user_id', name='server_access_uniq'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        CompatibleUUID(), ForeignKey('infra_servers.id', ondelete='CASCADE'), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='CASCADE'), index=True
    )
    permission: Mapped[str] = mapped_column(String(16), default='read')
    granted_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class InfraGpuMetric(Base):
    __tablename__ = 'infra_gpu_metrics'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        CompatibleUUID(), ForeignKey('infra_servers.id', ondelete='CASCADE'), index=True
    )
    gpu_index: Mapped[int] = mapped_column(SmallInteger)
    gpu_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mem_total_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mem_used_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    util_gpu_pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    util_mem_pct: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    temp_c: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    power_w: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    processes: Mapped[list] = mapped_column(CompatibleJSON(), default=list)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    collected_by: Mapped[str | None] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )


class InfraServiceSnapshot(Base):
    __tablename__ = 'infra_service_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    server_id: Mapped[str] = mapped_column(
        CompatibleUUID(), ForeignKey('infra_servers.id', ondelete='CASCADE'), index=True
    )
    unit_name: Mapped[str] = mapped_column(String(255))
    load_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sub_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class InfraAuditLog(Base):
    __tablename__ = 'infra_audit_log'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    actor_kind: Mapped[str] = mapped_column(String(16), default='user')
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    server_id: Mapped[str | None] = mapped_column(
        CompatibleUUID(), nullable=True, index=True
    )
    server_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    command_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    command_rendered: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class InfraPinnedContainer(Base):
    """User-scoped container focus list (pinned from Beszel UI for agents)."""

    __tablename__ = 'infra_pinned_containers'
    __table_args__ = (
        UniqueConstraint(
            'user_id',
            'host',
            'container_name',
            name='infra_pinned_containers_uniq',
        ),
        Index('infra_pinned_containers_user_idx', 'user_id'),
        Index('infra_pinned_containers_host_idx', 'host'),
    )

    id: Mapped[str] = mapped_column(
        CompatibleUUID(), primary_key=True, default=lambda: str(uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey('users.id', ondelete='CASCADE'), index=True
    )
    host: Mapped[str] = mapped_column(String(255))
    container_name: Mapped[str] = mapped_column(String(255))
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    image: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tags: Mapped[list] = mapped_column(CompatibleStringArray(), default=list)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    server_id: Mapped[str | None] = mapped_column(
        CompatibleUUID(),
        ForeignKey('infra_servers.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


_engine = None
SessionLocal = None


def init_db(database_url: str) -> None:
    global _engine, SessionLocal
    connect_args: dict = {}
    if database_url.startswith('sqlite'):
        connect_args = {'check_same_thread': False}
    _engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(_engine)
    if database_url.startswith('sqlite'):
        with _engine.begin() as conn:
            cols = {
                row[1]
                for row in conn.execute(text('PRAGMA table_info(users)')).fetchall()
            }
            if 'password_hash' not in cols:
                conn.execute(text('ALTER TABLE users ADD COLUMN password_hash TEXT'))
            conv_cols = {
                row[1]
                for row in conn.execute(
                    text('PRAGMA table_info(user_conversations)')
                ).fetchall()
            }
            for col, ddl in (
                (
                    'status',
                    "ALTER TABLE user_conversations ADD COLUMN status VARCHAR(32) DEFAULT 'active'",
                ),
                (
                    'source',
                    "ALTER TABLE user_conversations ADD COLUMN source VARCHAR(32) DEFAULT 'web'",
                ),
                (
                    'agent_profile',
                    'ALTER TABLE user_conversations ADD COLUMN agent_profile VARCHAR(128)',
                ),
                (
                    'llm_model',
                    'ALTER TABLE user_conversations ADD COLUMN llm_model VARCHAR(128)',
                ),
                (
                    'metadata',
                    "ALTER TABLE user_conversations ADD COLUMN metadata TEXT DEFAULT '{}'",
                ),
                (
                    'updated_at',
                    'ALTER TABLE user_conversations ADD COLUMN updated_at DATETIME',
                ),
                (
                    'last_activity_at',
                    'ALTER TABLE user_conversations ADD COLUMN last_activity_at DATETIME',
                ),
                (
                    'archived_at',
                    'ALTER TABLE user_conversations ADD COLUMN archived_at DATETIME',
                ),
            ):
                if col not in conv_cols:
                    conn.execute(text(ddl))
            {
                row[1]
                for row in conn.execute(
                    text('PRAGMA table_info(user_settings_blobs)')
                ).fetchall()
            }
            # payload may still be TEXT from older DBs; leave as-is for SQLite tests.


def get_db():
    if SessionLocal is None:
        raise RuntimeError('Database not initialized')
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
