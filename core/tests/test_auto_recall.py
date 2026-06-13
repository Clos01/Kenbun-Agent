"""Tests for automatic project-memory recall (Stream B / issue #4).

Covers the four guarantees signed off by the supervisor:
  (a) trivial input  -> recall skipped
  (b) relevant memory under the distance threshold -> injected and capped
  (c) Chroma raises  -> returns "" and does not propagate
  (d) KENBUN_AUTO_RECALL=0 -> no injection
plus the relevance (distance) filter that keeps irrelevant memories out.
"""
import unittest
from unittest import mock

from core.tools.memory import project_memory
from core.tools.infrastructure.config import settings


def _chroma_result(docs, distances, titles=None):
    """Builds a ChromaDB-shaped query result (lists nested one level)."""
    titles = titles or [f"Mem {i}" for i in range(len(docs))]
    return {
        "ids": [[f"id{i}" for i in range(len(docs))]],
        "documents": [list(docs)],
        "metadatas": [[{"title": t} for t in titles]],
        "distances": [list(distances)],
    }


class TestTrivialGuard(unittest.TestCase):
    def test_short_and_social_inputs_are_trivial(self):
        for q in ["", "hi", "hey", "ok", "thanks!", "yes", "no", "lol"]:
            self.assertTrue(project_memory._is_trivial_input(q), q)

    def test_substantive_inputs_are_not_trivial(self):
        for q in ["how do I fix the docker subnet collision", "explain the memory recall flow"]:
            self.assertFalse(project_memory._is_trivial_input(q), q)


class TestBuildContext(unittest.TestCase):
    def test_distance_filter_drops_irrelevant(self):
        # doc0 relevant (0.40), doc1 irrelevant (0.95) under a 0.75 ceiling.
        res = _chroma_result(["KEEP", "DROP"], [0.40, 0.95], ["Keep", "Drop"])
        with mock.patch.object(project_memory, "query_embeddings", return_value=res):
            out = project_memory.build_project_memory_context(
                "a substantive query", "/tmp/proj", distance_threshold=0.75
            )
        self.assertIn("KEEP", out)
        self.assertNotIn("DROP", out)

    def test_max_chars_hard_cap(self):
        big = "X" * 10_000
        res = _chroma_result([big], [0.10], ["Big"])
        with mock.patch.object(project_memory, "query_embeddings", return_value=res):
            out = project_memory.build_project_memory_context(
                "a substantive query", "/tmp/proj", max_chars=500
            )
        self.assertLessEqual(len(out), 500)

    def test_missing_distances_fails_open(self):
        # No "distances" key -> include the doc rather than guess.
        res = {"documents": [["INCLUDED"]], "metadatas": [[{"title": "T"}]]}
        with mock.patch.object(project_memory, "query_embeddings", return_value=res):
            out = project_memory.build_project_memory_context("a substantive query", "/tmp/proj")
        self.assertIn("INCLUDED", out)

    def test_chroma_failure_degrades_to_empty(self):
        with mock.patch.object(project_memory, "query_embeddings", side_effect=RuntimeError("chroma down")):
            out = project_memory.build_project_memory_context("a substantive query", "/tmp/proj")
        self.assertEqual(out, "")


class TestAutoRecallContext(unittest.TestCase):
    def test_trivial_input_skips_recall(self):
        with mock.patch.object(project_memory, "query_embeddings") as q:
            out = project_memory.auto_recall_context("hi", "/tmp/proj")
        self.assertEqual(out, "")
        q.assert_not_called()

    def test_flag_off_disables_recall(self):
        res = _chroma_result(["KEEP"], [0.10], ["Keep"])
        with mock.patch.object(settings, "KENBUN_AUTO_RECALL", False), \
             mock.patch.object(project_memory, "query_embeddings", return_value=res) as q:
            out = project_memory.auto_recall_context("a substantive query", "/tmp/proj")
        self.assertEqual(out, "")
        q.assert_not_called()

    def test_flag_on_injects_relevant_memory(self):
        res = _chroma_result(["KEEP"], [0.10], ["Keep"])
        with mock.patch.object(settings, "KENBUN_AUTO_RECALL", True), \
             mock.patch.object(settings, "MEMORY_RECALL_MAX_CHARS", 4000), \
             mock.patch.object(settings, "MEMORY_RECALL_DISTANCE_THRESHOLD", 0.75), \
             mock.patch.object(project_memory, "query_embeddings", return_value=res):
            out = project_memory.auto_recall_context("a substantive query", "/tmp/proj")
        self.assertIn("KEEP", out)


if __name__ == "__main__":
    unittest.main()
