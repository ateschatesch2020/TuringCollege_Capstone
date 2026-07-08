"""Unit tests for the api.py streaming routes that had no coverage before Phase 6 of
the backend refactor: POST /documents/ingest-paths, POST /form/search, POST /evaluate.
(GET/POST/DELETE /documents were already covered by test_documents.py, which also
exercises the sse_utils.sse_event() SSE framing these routes now share.)

Run with:
    pytest backend/tests/test_api_streaming_routes.py
"""

import json as _json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


def _parse_sse(text):
    events = []
    for block in text.split("\n\n"):
        line = block.strip()
        if line.startswith("data:"):
            try:
                events.append(_json.loads(line[5:].strip()))
            except _json.JSONDecodeError:
                pass
    return events


# Mock chatbot before importing api -- ChatbotManager is instantiated at module level
# in api.py and transitively pulls in tools/serpapi/ortools.
_chatbot_instance = MagicMock()
_real_chatbot_module = sys.modules.get("chatbot")
sys.modules["chatbot"] = MagicMock(
    ChatbotManager=MagicMock(return_value=_chatbot_instance)
)

from fastapi.testclient import TestClient  # noqa: E402
import api  # noqa: E402  (chatbot already mocked above)
from api import app  # noqa: E402

# api.py has already bound its own module-level `chatbot = ChatbotManager()` to our
# mock above; restore (or remove) the sys.modules entry now so this mock doesn't leak
# into other test modules collected later in the same pytest run that do
# `from chatbot import ChatbotManager` expecting the real module.
if _real_chatbot_module is not None:
    sys.modules["chatbot"] = _real_chatbot_module
else:
    del sys.modules["chatbot"]

client = TestClient(app)


# ---------------------------------------------------------------------------
# POST /documents/ingest-paths
# ---------------------------------------------------------------------------

class TestIngestPathsEndpoint(unittest.TestCase):

    def setUp(self):
        _chatbot_instance.reset_mock()

    def test_rejects_when_projects_dir_not_configured(self):
        with patch.dict(os.environ, {"PROJECTS_DIR": ""}):
            res = client.post("/documents/ingest-paths", json={"paths": ["a.pdf"], "session_id": "s1"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("PROJECTS_DIR", res.json()["detail"])

    def test_rejects_path_outside_projects_dir(self):
        with tempfile.TemporaryDirectory() as projects_dir, tempfile.TemporaryDirectory() as outside_dir:
            outside_file = os.path.join(outside_dir, "secret.pdf")
            with open(outside_file, "w") as f:
                f.write("x")
            with patch.dict(os.environ, {"PROJECTS_DIR": projects_dir}):
                res = client.post("/documents/ingest-paths", json={"paths": [outside_file], "session_id": "s1"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("No valid paths", res.json()["detail"])

    @patch("api.add_document_for_session", return_value=3)
    def test_ingests_a_valid_path_and_streams_completion(self, mock_add):
        with tempfile.TemporaryDirectory() as projects_dir, tempfile.TemporaryDirectory() as docs_dir:
            src_file = os.path.join(projects_dir, "report.pdf")
            with open(src_file, "w") as f:
                f.write("x")
            with patch.dict(os.environ, {"PROJECTS_DIR": projects_dir}), \
                 patch("api._SESSION_DOCS_DIR", docs_dir):
                res = client.post(
                    "/documents/ingest-paths",
                    json={"paths": [src_file], "session_id": "s1"},
                )

        self.assertEqual(res.status_code, 200)
        events = _parse_sse(res.text)
        complete = next(e for e in events if e.get("stage") == "Complete")
        self.assertEqual(complete["filename"], "report.pdf")
        self.assertEqual(complete["chunks"], 3)
        mock_add.assert_called_once()


# ---------------------------------------------------------------------------
# POST /form/search
# ---------------------------------------------------------------------------

class TestFormSearchEndpoint(unittest.TestCase):

    def test_streams_progress_then_result(self):
        def fake_search_with_progress(keyword, exact, contains):
            yield ("counting", None)
            yield ("progress", 50)
            yield ("done", f"results for {keyword}")

        with patch("api.form_manager.search_with_progress", side_effect=fake_search_with_progress):
            res = client.post("/form/search", json={"keyword": "report", "exact_match": False, "contains_name": True})

        self.assertEqual(res.status_code, 200)
        events = _parse_sse(res.text)
        stages = [e.get("stage") for e in events]
        self.assertEqual(stages, ["Counting files...", "Searching...", "Complete"])
        self.assertEqual(events[-1]["result"], "results for report")

    def test_streams_error_stage_on_failure(self):
        def fake_search_with_progress(keyword, exact, contains):
            raise RuntimeError("boom")
            yield  # pragma: no cover -- makes this a generator

        with patch("api.form_manager.search_with_progress", side_effect=fake_search_with_progress):
            res = client.post("/form/search", json={"keyword": "report", "exact_match": False, "contains_name": True})

        self.assertEqual(res.status_code, 200)
        events = _parse_sse(res.text)
        self.assertEqual(events[-1]["stage"], "Error")
        self.assertIn("boom", events[-1]["error"])


# ---------------------------------------------------------------------------
# POST /evaluate
# ---------------------------------------------------------------------------

class TestEvaluateEndpoint(unittest.TestCase):

    def setUp(self):
        _chatbot_instance.reset_mock()
        _chatbot_instance.get_session_embedding_model.return_value = None

    def test_404_when_document_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("api._SESSION_DOCS_DIR", tmpdir):
                res = client.post(
                    "/evaluate",
                    json={"filename": "missing.pdf", "session_id": "s1", "num_questions": 5},
                )
        self.assertEqual(res.status_code, 404)

    def test_streams_progress_then_complete_with_results(self):
        async def fake_evaluate_document(**kwargs):
            await kwargs["progress_cb"]("Generating test questions...", 10)
            return [{"question": "q1", "expected_answer": "a1", "rag_answer": "a1"}]

        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = os.path.join(tmpdir, "s1")
            os.makedirs(session_dir)
            doc_path = os.path.join(session_dir, "report.pdf")
            with open(doc_path, "w") as f:
                f.write("x")
            with patch("api._SESSION_DOCS_DIR", tmpdir), \
                 patch("rag.ragas_evaluator.evaluate_document", side_effect=fake_evaluate_document):
                res = client.post(
                    "/evaluate",
                    json={"filename": "report.pdf", "session_id": "s1", "num_questions": 1},
                )

        self.assertEqual(res.status_code, 200)
        events = _parse_sse(res.text)
        stages = [e.get("stage") for e in events]
        self.assertIn("Generating test questions...", stages)
        complete = next(e for e in events if e.get("stage") == "Complete")
        self.assertEqual(complete["results"][0]["question"], "q1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
