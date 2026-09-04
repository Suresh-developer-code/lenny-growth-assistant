# Architecture — The Lenny Growth Assistant

## 1. System overview

```
                         ┌────────────────────────────┐
                         │        Frontend (Next.js)    │
                         │  ChatPane │ ArtifactViewer    │
                         └──────────────┬───────────────┘
                                         │ REST + SSE
                         ┌──────────────▼───────────────┐
                         │        FastAPI Backend        │
                         │  /api/sessions /api/chat       │
                         │  /api/health                   │
                         │  ┌───────────────────────────┐ │
                         │  │ Agent / Skill Router        │ │
                         │  │  - Grounded QA               │ │
                         │  │  - Ship30Writer               │ │
                         │  │  - ArtifactGenerator          │ │
                         │  └───────────────┬─────────────┘ │
                         │  ┌───────────────▼─────────────┐ │
                         │  │ TranscriptRetriever (pgvector)│ │
                         │  └───────────────┬─────────────┘ │
                         │  ┌───────────────▼─────────────┐ │
                         │  │ LLMProvider (Ollama | Claude) │ │
                         │  └───────────────────────────────┘ │
                         └──────────────┬───────────────────┘
                                         │
                    ┌────────────────────┼───────────────────┐
                    │                    │                    │
             ┌──────▼──────┐     ┌───────▼───────┐    ┌───────▼───────┐
             │ PostgreSQL   │     │ Ollama (local) │    │ Anthropic API  │
             │ + pgvector   │     │ :11434          │    │ (cloud, opt-in)│
             └─────────────┘     └────────────────┘    └────────────────┘
```

## 2. Database schema

Postgres 16 + `pgvector` extension.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sessions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        TEXT NOT NULL DEFAULT 'New session',
    user_metadata JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content      TEXT NOT NULL,
    sources      JSONB NOT NULL DEFAULT '[]',
    provider     TEXT,               -- 'ollama' | 'anthropic'
    mode         TEXT DEFAULT 'qa',  -- 'qa' | 'ship30' | 'artifact'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE artifacts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id   UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('markdown', 'html')),
    title        TEXT NOT NULL DEFAULT 'Untitled artifact',
    content      TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transcript_chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_title TEXT NOT NULL,
    guest_name    TEXT,
    source_url    TEXT,
    timestamp_ref TEXT,
    chunk_text    TEXT NOT NULL,
    chunk_index   INT NOT NULL,
    embedding     vector(384),   -- all-MiniLM-L6-v2 / nomic-embed-text dim
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transcript_chunks_hnsw
    ON transcript_chunks USING hnsw (embedding vector_cosine_ops);
```

`sources` on `messages` is a JSONB array of `{episode, guest, timestamp, score}` so the frontend can render citations without re-querying the vector store, and so citation accuracy can be audited offline.

## 3. Ingestion / retrieval flow

1. `scripts/download_transcripts.py` pulls raw episode files from `TRANSCRIPT_SOURCE_URL` (or reads `backend/data/sample_transcripts/` when offline/demo mode) into a local staging directory.
2. `scripts/ingest.py`:
   - Parses front-matter (`guest`, `title`, `date`) from each file.
   - Splits body text with a recursive character splitter, target 500–800 tokens, 100-token overlap, so chunks don't cut mid-idea and adjacent chunks retain context.
   - Calls the configured embedding function (`sentence-transformers/all-MiniLM-L6-v2` by default, or Ollama's `nomic-embed-text` if `EMBEDDING_PROVIDER=ollama`) for each chunk.
   - Inserts rows into `transcript_chunks`, tagging each with its source episode/guest/timestamp so every retrieval result is traceable back to a specific point in a specific episode.
   - Is idempotent per source file (re-running re-ingestion replaces that episode's chunks rather than duplicating them).
3. At query time, `TranscriptRetriever.retrieve_relevant_chunks()` embeds the query, runs an HNSW cosine-similarity search (`top_k=4–6`), and drops results under `similarity_threshold=0.65` (configurable via `RETRIEVAL_SIMILARITY_THRESHOLD`).
4. If **zero** chunks clear the threshold, the agent is instructed to say the archive doesn't cover the question rather than answering from parametric knowledge — this is enforced in the system prompt, not just hoped for, and unit-tested in `tests/test_retrieval.py`.

## 4. Agent / skill routing

A single `/api/chat` endpoint takes a `mode` field (`qa` default, `ship30`, `artifact`) rather than separate endpoints per skill, so the frontend has one integration point and skills can be composed (e.g., a `ship30` request still runs the same retriever first).

- **Grounded QA** (`app/api/chat.py` → default path): retrieve → build citation-enforcing prompt → stream tokens.
- **Ship30Writer** (`app/skills/ship30_writer.py`): retrieve (wider k) → build the Ship 30 structural prompt (hook / skimmable formatting / grounded claims / actionable takeaway) → generate as one artifact rather than streamed chat tokens, since it's a document, not a conversational reply.
- **ArtifactGenerator** (`app/skills/artifact_generator.py`): wraps whatever the active skill produced in a `<artifact type="markdown|html" title="...">` envelope that the frontend parses out of the stream and detaches into the Artifact Viewer, leaving a short acknowledgment in the chat transcript itself.

## 5. Model routing (dual provider layer)

`LLMProviderInterface` (`app/providers/base.py`) defines one async streaming method, `generate_response()`. Two concrete drivers implement it:

- `OllamaProvider` — calls `POST {OLLAMA_BASE_URL}/api/chat` with `stream: true`, defaults to `llama3.2:3b`.
- `AnthropicProvider` — calls the Anthropic Messages API with streaming.

`app/providers/factory.py` resolves which driver to use per-request:

1. Explicit `provider` field on the chat request (frontend dropdown), if present.
2. Else `DEFAULT_LLM_PROVIDER` env var.
3. Else falls back to `ollama` (the required local path always works without any API key).

If the resolved cloud provider has no API key configured, the factory raises a structured `ProviderUnavailableError` that the API layer turns into a `503` with a clear message — **it never silently falls back to the other provider**, because silently switching providers mid-conversation would be a confusing, hard-to-debug UX (a user believing they're testing the cloud model but actually getting local output). Fallback behavior is therefore: **explicit failure, not implicit substitution** — documented in the README's troubleshooting section.

## 6. API endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/sessions` | Create a session, returns `id` |
| `GET` | `/api/sessions/{id}` | Fetch session + message history |
| `GET` | `/api/sessions` | List recent sessions |
| `POST` | `/api/chat` | Streaming (SSE) chat/skill request |
| `GET` | `/api/health` | Per-dependency health (db, vector index, ollama, cloud key) |

Request/response contracts are `pydantic v2` models in `app/models/schemas.py`; validation errors return RFC-7807-style structured JSON (`{type, title, detail, status}`) via a global FastAPI exception handler, not raw tracebacks.

## 7. Artifact rendering security

Threat model: transcript content is untrusted-ish (public but unvetted), and LLM output is **always** untrusted, since prompt injection inside a transcript chunk could attempt to make the model emit malicious HTML/JS.

Controls, in layers:

1. **Sanitization**: every HTML artifact is run through `DOMPurify` on the frontend before being placed in `srcdoc`. This strips `<script>`-adjacent attack vectors like `onerror=`, `javascript:` URLs, etc. We keep `<style>`/`<script>` tags allowed (artifacts are meant to be interactive, e.g. a small calculator) — the isolation guarantee comes from the sandbox, not from banning scripts outright.
2. **Iframe sandboxing**: the artifact is mounted via `<iframe sandbox="allow-scripts" srcDoc={...}>` — deliberately **omitting** `allow-same-origin`. Per the HTML spec, this combination means scripts execute inside the iframe (so interactive artifacts work) but the iframe is placed in a unique, opaque origin: it **cannot** read the parent page's cookies, `localStorage`, or DOM, and cannot navigate `window.top`. This is the standard technique used by CodeSandbox/CodePen-style embeds and by Claude's own Artifacts.
3. **No network credentials in scope**: the iframe has no access to the app's auth/session cookies (different origin), so even a successful script injection inside the sandbox cannot exfiltrate session data via `fetch`+credentials — it could only make anonymous, credential-less requests, same as any third-party page.
4. **CSP** on the parent app additionally restricts `frame-src`/`script-src` to prevent the artifact iframe content from being swapped for an externally-hosted malicious page.
5. **What we explicitly do NOT try to guarantee**: fully preventing the artifact from making arbitrary outbound `fetch` calls (a sandboxed iframe without `allow-same-origin` can still issue network requests, it just can't read the parent's storage or cookies). If this were a production system handling sensitive data, we'd add a `Content-Security-Policy: connect-src 'none'` inside the artifact's own document (already included in the generated HTML template) to close that gap too.

## 8. Deployment topology

- `docker-compose.yml` defines four services: `db` (pgvector/pgvector:pg16), `backend` (FastAPI/uvicorn), `frontend` (Next.js), and an optional `ollama` service for environments that don't already have Ollama running natively.
- `backend` depends on `db`'s healthcheck before starting; `/api/health` distinguishes "DB down" (hard failure, 503) from "Ollama down" (soft failure — cloud path may still work, 200 with a warning field) from "Cloud key missing" (soft, informational only if `DEFAULT_LLM_PROVIDER=ollama`).
- All configuration is env-var driven (`.env`, loaded via `pydantic-settings`), with `.env.example` documenting every variable, safe defaults, and which are required vs. optional.
- Structured logs (`structlog`/JSON) tag every request with a `request_id`, `session_id`, and `provider`, so a client engineer can grep logs for one conversation across retrieval, generation, and persistence steps.

## 9. Component boundaries

- **`app/providers/`** — knows nothing about retrieval, sessions, or skills. Pure "talk to an LLM" abstraction.
- **`app/rag/`** — knows nothing about HTTP or the API layer. Pure "given a query, return ranked chunks."
- **`app/skills/`** — orchestrates providers + rag into a specific product behavior (QA, essay, artifact). This is where prompt engineering lives, isolated from transport concerns.
- **`app/api/`** — HTTP/SSE boundary only: validates requests, calls skills, persists results, streams responses. No prompt strings live here.
- **`app/database.py` / `app/models/`** — persistence only.

This separation is what lets the model/provider be swapped, or a new skill added, without touching the API layer or the DB layer.
