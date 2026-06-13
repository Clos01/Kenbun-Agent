"""Tests for the SQLite chat store (scalability issue #3).

Focus on the two guarantees that the old JSON+lockfile store could not make:
  * concurrent writers never lose messages (the original O(n)-rewrite race);
  * the legacy chat_sessions.json migrates faithfully and is preserved as
    a .migrated rollback artifact.
"""
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from core.tools.infrastructure.config import settings
from core.tools.utils import chat_store_sqlite


class _TempStore(unittest.TestCase):
    """Base: point the store at a throwaway brain_health dir per test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kenbun_chat_"))
        self._patch = mock.patch.object(settings, "BRAIN_HEALTH_DIR", self.tmp)
        self._patch.start()
        chat_store_sqlite._migration_done = False

    def tearDown(self):
        self._patch.stop()
        chat_store_sqlite._migration_done = False
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestConcurrency(_TempStore):
    def test_parallel_writers_lose_no_messages(self):
        session = chat_store_sqlite.create_session("Concurrency")
        sid = session["id"]
        n = 20

        def writer(i):
            chat_store_sqlite.add_message_to_session(sid, "user", f"msg-{i}")

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        fetched = chat_store_sqlite.get_session(sid)
        # initial greeting + n user messages, none dropped.
        self.assertEqual(len(fetched["messages"]), n + 1)
        contents = {m["content"] for m in fetched["messages"] if m["sender"] == "user"}
        self.assertEqual(contents, {f"msg-{i}" for i in range(n)})


class TestMigration(_TempStore):
    def test_legacy_json_imports_and_is_preserved(self):
        legacy = self.tmp / "chat_sessions.json"
        legacy.write_text(
            json.dumps(
                [
                    {
                        "id": "session_legacy01",
                        "title": "Old Session",
                        "timestamp": "2024-01-01T00:00:00",
                        "messages": [
                            {"id": "initial", "sender": "kenbun", "content": "hello", "timestamp": "t0"},
                            {"id": "msg_a", "sender": "user", "content": "old question", "timestamp": "t1"},
                        ],
                    }
                ]
            ),
            encoding="utf-8",
        )

        # First store access triggers the one-time import.
        summaries = chat_store_sqlite.list_sessions()
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["id"], "session_legacy01")

        fetched = chat_store_sqlite.get_session("session_legacy01")
        self.assertEqual(len(fetched["messages"]), 2)
        self.assertEqual(fetched["messages"][1]["content"], "old question")

        # Legacy file preserved as rollback artifact, original removed.
        self.assertFalse(legacy.exists())
        self.assertTrue((self.tmp / "chat_sessions.json.migrated").exists())

    def test_no_double_import_when_db_populated(self):
        chat_store_sqlite.create_session("Existing")
        # Drop a legacy file AFTER the DB already has data; reset the one-shot guard.
        (self.tmp / "chat_sessions.json").write_text(
            json.dumps([{"id": "session_should_not_import", "title": "X", "messages": []}]),
            encoding="utf-8",
        )
        chat_store_sqlite._migration_done = False

        ids = {s["id"] for s in chat_store_sqlite.list_sessions()}
        self.assertNotIn("session_should_not_import", ids)


if __name__ == "__main__":
    unittest.main()
