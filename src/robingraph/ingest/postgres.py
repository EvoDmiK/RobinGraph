"""PostgreSQL control-plane settings and forward-only schema migrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import os
import re


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MIGRATION_NAME = re.compile(r"^(?P<version>[0-9]{4})_[a-z0-9_]+\.sql$")


@dataclass(frozen=True)
class PostgresSettings:
    host: str
    port: int
    database: str
    schema: str
    username: str
    password: str = field(repr=False)
    sslmode: str

    @classmethod
    def from_environment(cls) -> "PostgresSettings":
        values = {
            "host": os.getenv("ROBINGRAPH_PG_HOST", "").strip(),
            "database": os.getenv("ROBINGRAPH_PG_DATABASE", "").strip(),
            "schema": os.getenv("ROBINGRAPH_PG_SCHEMA", "ingest").strip(),
            "username": os.getenv("ROBINGRAPH_PG_USERNAME", "").strip(),
            "password": os.getenv("ROBINGRAPH_PG_PASSWORD", ""),
            "sslmode": os.getenv("ROBINGRAPH_PG_SSLMODE", "prefer").strip(),
        }
        missing = [
            variable
            for field, variable in (
                ("host", "ROBINGRAPH_PG_HOST"),
                ("database", "ROBINGRAPH_PG_DATABASE"),
                ("username", "ROBINGRAPH_PG_USERNAME"),
                ("password", "ROBINGRAPH_PG_PASSWORD"),
            )
            if not values[field]
        ]
        if missing:
            raise ValueError(f"Missing required PostgreSQL environment variables: {', '.join(missing)}")
        try:
            port = int(os.getenv("ROBINGRAPH_PG_PORT", "5432"))
        except ValueError as error:
            raise ValueError("ROBINGRAPH_PG_PORT must be an integer") from error
        if not 1 <= port <= 65535:
            raise ValueError("ROBINGRAPH_PG_PORT must be between 1 and 65535")
        if not _IDENTIFIER.fullmatch(values["schema"]):
            raise ValueError("ROBINGRAPH_PG_SCHEMA must be a PostgreSQL identifier")
        if values["sslmode"] not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
            raise ValueError("ROBINGRAPH_PG_SSLMODE is invalid")
        if os.getenv("ROBINGRAPH_POSTGRES_INTEGRATION_TESTS") == "1" and "test" not in values["database"].lower():
            raise ValueError("PostgreSQL integration tests require a database name containing 'test'")
        return cls(port=port, **values)

    def connection_kwargs(self) -> dict[str, str | int]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.username,
            "password": self.password,
            "sslmode": self.sslmode,
            "application_name": "robingraph-migrations",
        }


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    sql: str
    checksum: str


@dataclass(frozen=True)
class MigrationReport:
    database: str
    schema: str
    applied: tuple[str, ...]
    already_current: tuple[str, ...]


def migration_root() -> Path:
    return Path(__file__).with_name("migrations")


def discover_migrations(root: Path | None = None) -> tuple[Migration, ...]:
    migrations: list[Migration] = []
    for path in sorted((root or migration_root()).glob("*.sql")):
        match = _MIGRATION_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError(f"Invalid PostgreSQL migration filename: {path.name}")
        body = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=match.group("version"),
                name=path.name,
                sql=body,
                checksum=sha256(body.encode("utf-8")).hexdigest(),
            )
        )
    versions = [migration.version for migration in migrations]
    if len(versions) != len(set(versions)):
        raise ValueError("PostgreSQL migration versions must be unique")
    return tuple(migrations)


def apply_migrations(settings: PostgresSettings) -> MigrationReport:
    """Apply pending migrations atomically under a database-scoped advisory lock."""

    import psycopg
    from psycopg import sql

    applied: list[str] = []
    current: list[str] = []
    with psycopg.connect(**settings.connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(settings.schema)))
            cursor.execute(sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(sql.Identifier(settings.schema)))
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s))",
                (f"robingraph:migrations:{settings.database}:{settings.schema}",),
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS _schema_migration (
                    version text PRIMARY KEY,
                    name text NOT NULL UNIQUE,
                    checksum char(64) NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute("SELECT version, checksum FROM _schema_migration")
            known = dict(cursor.fetchall())
            for migration in discover_migrations():
                checksum = known.get(migration.version)
                if checksum is not None:
                    if checksum != migration.checksum:
                        raise ValueError(
                            f"Migration {migration.name} changed after it was applied; "
                            "create a new forward migration instead"
                        )
                    current.append(migration.name)
                    continue
                cursor.execute(migration.sql)
                cursor.execute(
                    "INSERT INTO _schema_migration (version, name, checksum) VALUES (%s, %s, %s)",
                    (migration.version, migration.name, migration.checksum),
                )
                applied.append(migration.name)
    return MigrationReport(settings.database, settings.schema, tuple(applied), tuple(current))


def verify_schema(settings: PostgresSettings) -> tuple[str, ...]:
    """Return required ingest tables, failing when the schema is incomplete."""

    import psycopg

    required = {
        "source_dataset",
        "source_release",
        "ingestion_run",
        "source_record",
        "quarantine_item",
        "ingest_state",
        "outbox_event",
    }
    with psycopg.connect(**settings.connection_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = %s",
                (settings.schema,),
            )
            present = {row[0] for row in cursor.fetchall()}
    missing = sorted(required - present)
    if missing:
        raise ValueError(f"PostgreSQL ingest schema is incomplete; missing: {', '.join(missing)}")
    return tuple(sorted(required))
