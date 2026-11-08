"""Apply the bundled schema before an API instance starts serving requests."""
from hashlib import sha256
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql").read_text()
VERSION = sha256(SCHEMA.encode()).hexdigest()


def ensure_schema(db):
    # Concurrent application starts must finish the upgrade in a single transaction.
    db.execute("SELECT pg_advisory_xact_lock(507716)")
    db.execute("""CREATE TABLE IF NOT EXISTS pm_schema_version(
        id integer PRIMARY KEY CHECK (id=1), version text NOT NULL)""")
    row = db.execute("SELECT version FROM pm_schema_version WHERE id=1").fetchone()
    if row and row["version"] == VERSION:
        return
    db.execute(SCHEMA)
    db.execute("""INSERT INTO pm_schema_version(id,version) VALUES (1,%s)
        ON CONFLICT(id) DO UPDATE SET version=excluded.version""", (VERSION,))


def migrate():
    from .db import database
    with database() as db:
        ensure_schema(db)


if __name__ == "__main__":
    migrate()
