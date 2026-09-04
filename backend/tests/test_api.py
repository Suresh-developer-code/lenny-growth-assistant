"""API-layer tests.

Split into:
  - Pure-function tests for artifact envelope parsing (no DB/network needed).
  - A FastAPI TestClient smoke test against endpoints that don't require a
    live DB (docs, root).
  - Integration tests (require RUN_INTEGRATION_TESTS=1 + docker-compose up)
    that exercise /api/sessions and /api/chat end-to-end against a real
    Postgres + Ollama, per the manual test plan in README.md.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.skills.artifact_generator import extract_artifact, strip_artifact_tags, wrap_markdown_artifact

client = TestClient(app)


def test_root_endpoint_smoke():
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"


def test_openapi_docs_available():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/api/chat" in resp.json()["paths"]
    assert "/api/sessions" in resp.json()["paths"]
    assert "/api/health" in resp.json()["paths"]


def test_chat_missing_session_returns_422_on_bad_payload():
    resp = client.post("/api/chat", json={"message": "hi"})  # missing session_id
    assert resp.status_code == 422
    body = resp.json()
    assert body["type"] == "validation_error"


# ---------- Artifact envelope parsing (pure functions) ----------

HTML_ARTIFACT_RESPONSE = (
    'Sure, here you go.\n\n'
    '<artifact type="html" title="Pricing Calculator">'
    "<!DOCTYPE html><html><body><h1>Calc</h1></body></html>"
    "</artifact>"
)


def test_extract_artifact_parses_type_title_and_content():
    parsed = extract_artifact(HTML_ARTIFACT_RESPONSE)
    assert parsed is not None
    assert parsed.artifact_type == "html"
    assert parsed.title == "Pricing Calculator"
    assert "<h1>Calc</h1>" in parsed.content


def test_extract_artifact_returns_none_when_absent():
    assert extract_artifact("Just a normal chat reply, no artifact here.") is None


def test_strip_artifact_tags_leaves_short_acknowledgment_not_full_html():
    stripped = strip_artifact_tags(HTML_ARTIFACT_RESPONSE)
    assert "<!DOCTYPE html>" not in stripped
    assert "Pricing Calculator" in stripped


def test_wrap_markdown_artifact_roundtrips_through_extract():
    wrapped = wrap_markdown_artifact("My Essay", "# Hello\n\nBody text.")
    parsed = extract_artifact(wrapped)
    assert parsed is not None
    assert parsed.artifact_type == "markdown"
    assert parsed.title == "My Essay"
    assert "Body text." in parsed.content


@pytest.mark.integration
def test_full_session_and_chat_flow_against_live_stack():
    """Requires: docker-compose up, transcripts ingested, Ollama model pulled.
    Run with: RUN_INTEGRATION_TESTS=1 pytest -m integration
    """
    import os

    if os.environ.get("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run against a live stack")

    create_resp = client.post("/api/sessions", json={"title": "Integration test"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    chat_resp = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "What did Casey Winters say about growth loops?"},
    )
    assert chat_resp.status_code == 200
    assert "text/event-stream" in chat_resp.headers["content-type"]
