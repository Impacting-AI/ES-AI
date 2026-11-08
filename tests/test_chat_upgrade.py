"""Older installations should open saved conversations after an application upgrade."""
import sqlite3
import unittest
from server import migrate


class UpgradeTests(unittest.TestCase):
    def test_old_chat_survives_startup_and_restart(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE chat_threads(id text, pid text, title text, updated text);
            CREATE TABLE messages(thread_id text,pid text,created text);
            INSERT INTO chat_threads VALUES('thread','project','Scope','2026-11-07');
            INSERT INTO messages VALUES('thread','project','2026-11-01');
        """)
        with self.assertRaisesRegex(sqlite3.OperationalError, 'no such column'):
            db.execute("SELECT t.created FROM chat_threads t")
        migrations = []
        class Fixture:
            def execute(self, sql, args=()):
                if 'pg_advisory_xact_lock' in sql:
                    return
                if sql == migrate.SCHEMA:
                    migrations.append(1)
                    # SQLite equivalent DDL; execute the actual production data backfill.
                    db.execute('ALTER TABLE chat_threads ADD COLUMN created text')
                    backfill = next(s for s in sql.split(';') if 'UPDATE chat_threads t SET created=' in s)
                    db.execute(backfill.replace('chat_threads t SET','chat_threads AS t SET'))
                    return
                return db.execute(sql.replace('%s','?'),args)
        with db:
            migrate.ensure_schema(Fixture())
        with db:
            migrate.ensure_schema(Fixture())
        self.assertEqual(migrations,[1])
        self.assertEqual(tuple(db.execute('SELECT title,created FROM chat_threads').fetchone()),('Scope','2026-11-01'))

    def test_chat_error_reference_excludes_payload(self):
        from server.chat_errors import chat_error
        with self.assertLogs("server.chat_errors",level="ERROR") as captured:
            detail=chat_error("generate",ValueError("private customer message"))
        self.assertIn(detail.split()[-1].rstrip("."),captured.output[0])
        self.assertNotIn("private customer message",captured.output[0]+detail)

    def test_schema_failure_cannot_publish_ready_version(self):
        from unittest.mock import MagicMock
        db=MagicMock()
        db.execute.return_value.fetchone.return_value=None
        def execute(sql,*args):
            if sql==migrate.SCHEMA:
                raise RuntimeError("DDL failed")
            return cursor
        cursor=db.execute.return_value
        db.execute.side_effect=execute
        with self.assertRaises(RuntimeError):
            migrate.ensure_schema(db)
        self.assertFalse(any('INSERT INTO pm_schema_version' in call.args[0] for call in db.execute.call_args_list))
