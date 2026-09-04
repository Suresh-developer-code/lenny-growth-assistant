# The Lenny Growth Assistant

A grounded, RAG-powered assistant over *Lenny's Podcast* transcripts — ask product/growth questions
with citations, turn answers into a Ship 30 for 30–style essay, or generate a rendered Markdown/HTML
artifact, all inside a Claude-Artifacts-style two-pane UI.

Built as a Forward Deployed Engineer take-home. See `docs/PRD.md`, `docs/architecture.md`, and
`docs/design.md` for the full discovery brief, system design, and UX rationale.

## 1. Architecture overview

```
Next.js (chat + artifact viewer) → FastAPI (agent/skill routing) → Postgres + pgvector (retrieval)
                                                                  → Ollama (local) or Anthropic (cloud)
```

- **Backend**: FastAPI, SQLAlchemy (async), pgvector-backed retrieval, a provider-agnostic LLM
  interface (Ollama local / Anthropic cloud), and three skills: grounded Q&A, a Ship 30 for 30 essay
  writer, and an artifact generator/parser.
- **Frontend**: Next.js (App Router) + Tailwind, a two-pane chat/artifact layout, SSE streaming, and
  a sandboxed `<iframe>` artifact viewer.
- **Data**: Postgres 16 + `pgvector`, three tables (`sessions`, `messages`, `artifacts`) plus
  `transcript_chunks` for the vector index.

Full detail: [`docs/architecture.md`](docs/architecture.md).

## 2. Prerequisites

- Docker & Docker Compose v24+ (recommended path), **or** Python 3.11+ and Node 18/20 for running
  services natively.
- [Ollama](https://ollama.com) installed on your **host machine** (not just in a container) — the
  mandatory local demo talks to it at `http://localhost:11434`.
- ~15 GB free disk (model weights + embeddings).
- An Anthropic API key **only** if you want to demo the cloud path — entirely optional.

## 3. One-command startup (Docker Compose)

```bash
git clone <this-repo>
cd lenny-growth-assistant
cp .env.example .env

# 1. Start Ollama on the host and pull the demo model
ollama serve &
ollama pull llama3.2:3b

# 2. Bring up db + backend + frontend
docker compose up --build

# 3. In another terminal: initialize the DB schema, then ingest the sample transcripts
docker compose exec backend python -m scripts.init_db
docker compose exec backend python -m scripts.download_transcripts
docker compose exec backend python -m scripts.ingest
```

Then open:
- Frontend: http://localhost:3000
- Backend docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

## 4. Running natively (no Docker)

```bash
# --- Database ---
# Any Postgres 16 with the pgvector extension works. Easiest options:
#   a) `docker run -e POSTGRES_PASSWORD=password123 -p 5432:5432 pgvector/pgvector:pg16`
#   b) a free Supabase or Railway Postgres instance (both support pgvector) — put its
#      connection string in DATABASE_URL in .env

# --- Backend ---
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # edit DATABASE_URL etc as needed
python -m scripts.init_db
python -m scripts.download_transcripts
python -m scripts.ingest
uvicorn app.main:app --reload --port 8000

# --- Frontend (separate terminal) ---
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

## 5. Environment variables

See [`.env.example`](.env.example) for the full, commented list. Required vs optional:

| Variable | Required? | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | points at docker-compose's `db` service | must use `postgresql+asyncpg://` |
| `DEFAULT_LLM_PROVIDER` | Yes | `ollama` | must be `ollama` for the local demo |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Yes (for local demo) | `http://localhost:11434` / `llama3.2:3b` | |
| `ANTHROPIC_API_KEY` | No | unset | only needed to demo the cloud path |
| `EMBEDDING_PROVIDER` | No | `sentence_transformers` | runs locally, no key/network needed |
| `TRANSCRIPT_SOURCE_URL` | No | unset | unset → ingest bundled sample transcripts |
| `NEXT_PUBLIC_API_URL` | Yes (frontend) | `http://localhost:8000` | |

## 6. Local vs cloud model setup

**Local (Ollama) — required for the demo:**
```bash
ollama pull llama3.2:3b       # default, comfortable on 16GB RAM
# or, if your machine can handle it:
ollama pull llama3.1:8b
ollama pull mistral:7b
```
Set `OLLAMA_MODEL` in `.env` to match whichever you pulled.

**Cloud (Anthropic) — optional:**
```bash
# in .env
ANTHROPIC_API_KEY=sk-ant-...
```
The provider dropdown in the UI (or the `provider` field on `POST /api/chat`) switches between them
per-request — no restart needed. If you request a provider that isn't configured (e.g. Anthropic with
no key), the API returns a `503` with a clear message; it never silently falls back to the other
provider (see `docs/architecture.md §5` for why).

## 7. Ingestion

```bash
python -m scripts.download_transcripts   # stages transcript files into backend/data/staged/
python -m scripts.ingest                 # chunks, embeds, and upserts into pgvector
python -m scripts.ingest --file casey-winters-growth-loops.md   # single-file re-ingest
```

By default (no `TRANSCRIPT_SOURCE_URL`), this ingests the three sample transcripts bundled in
`backend/data/sample_transcripts/` (Casey Winters on growth loops, Julie Zhuo on PM onboarding, Elena
Verna on PLG pricing) — enough to exercise the full retrieve→cite→answer path end to end. Point
`TRANSCRIPT_SOURCE_URL` at a real transcript repository/API to ingest the full archive; see the
comments in `backend/scripts/download_transcripts.py` for the expected format.

## 8. Tests

```bash
cd backend
pip install -r requirements.txt
pytest                              # 20 unit tests — no live DB/Ollama needed
RUN_INTEGRATION_TESTS=1 pytest -m integration   # requires docker compose up + ingested data
```

Unit tests cover: retrieval/prompt-building logic (including the anti-hallucination "no context found"
contract), the provider factory's fail-loud-not-fallback behavior, and artifact envelope parsing.

### Manual UI test plan

1. **New session**: load the app, confirm a session is created and a reload preserves it (same
   session ID, history restored).
2. **Grounded answer**: ask "What does Casey Winters say about growth loops?" → expect an answer with
   at least one citation chip referencing that episode.
3. **Out-of-domain question**: ask something the sample corpus doesn't cover (e.g. "What's the best
   way to configure Kubernetes autoscaling?") → expect the explicit "I do not have sufficient
   information..." response, not a fabricated answer.
4. **Follow-up**: ask a pronoun-dependent follow-up ("what else did they say about that?") → confirm
   session context carries over.
5. **Ship 30 essay**: click "Ship 30 essay" mode, ask it to write up the growth-loops topic → confirm
   the Artifact panel opens with a ~1,100–1,400 word Markdown essay with headers and a closing
   takeaway.
6. **HTML artifact**: switch to "Build artifact" mode, ask for a simple comparison table as HTML →
   confirm it renders in the sandboxed iframe, and that view-source shows no `allow-same-origin` on
   the iframe's `sandbox` attribute.
7. **Provider switch**: toggle the model dropdown to Claude (with a key configured) mid-session,
   confirm the next message's badge shows `anthropic` as the serving provider.
8. **Ollama down**: stop `ollama serve`, refresh, confirm the dropdown shows Ollama as unavailable
   with an inline reason, and that sending a message returns a clear error, not a hang.
9. **Health endpoint**: hit `/api/health` with the DB stopped → expect HTTP 503 and
   `dependencies[].ok == false` for `database`.
10. **Mobile layout**: resize below 640px, confirm the Chat/Artifact tab switcher replaces the
    two-pane layout.

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Could not reach Ollama at http://localhost:11434` | Ollama not running, or running only inside a container the backend container can't see | Run `ollama serve` on the **host**; the backend reaches it via `host.docker.internal` (already configured in `docker-compose.yml`) |
| `Ollama returned HTTP 404` / model errors | Model not pulled | `ollama pull llama3.2:3b` (or whatever `OLLAMA_MODEL` is set to) |
| `ANTHROPIC_API_KEY is not set` | Requested the cloud provider without configuring a key | Add the key to `.env`, or select Ollama in the dropdown |
| `/api/health` returns `status: "down"` | Postgres not reachable | Check `docker compose ps`, confirm `DATABASE_URL` matches the running instance |
| Retrieval returns nothing / all answers say "insufficient information" | Transcripts not ingested yet | Run `scripts/download_transcripts.py` then `scripts/ingest.py` |
| Frontend shows "Backend unavailable" | `NEXT_PUBLIC_API_URL` wrong, or CORS blocking the request | Confirm the backend is running on that URL and `CORS_ALLOW_ORIGINS` includes the frontend's origin |
| Artifact panel shows raw text instead of rendering | The model didn't emit a well-formed `<artifact type="...">` tag | Check backend logs for the raw response; the system prompt in `app/skills/artifact_generator.py` defines the exact expected format — small/local models occasionally deviate from it |
| Slow first response | Cold-starting the embedding model or the local LLM | Expected on first request per process; subsequent requests are faster |

## 10. Project structure

```
lenny-growth-assistant/
├── docker-compose.yml
├── .env.example
├── README.md
├── docs/                    PRD, architecture, design
├── agent_transcripts/       coding-agent session logs
├── backend/
│   ├── app/
│   │   ├── main.py, config.py, database.py
│   │   ├── models/          SQLAlchemy models + Pydantic schemas
│   │   ├── providers/       Ollama + Anthropic behind one interface
│   │   ├── rag/             embeddings + pgvector retriever
│   │   ├── skills/          grounded QA, Ship 30 writer, artifact generator
│   │   └── api/             sessions, chat (SSE), health routes
│   ├── scripts/              download_transcripts.py, ingest.py, init_db.py
│   ├── data/sample_transcripts/   3 bundled sample episodes
│   └── tests/
└── frontend/
    └── src/
        ├── app/              layout, page, global styles
        ├── components/       Chat/*, Artifact/*
        ├── hooks/             useChatStream.ts
        └── lib/               api.ts
```

## 11. Known limitations / what a client engineer should know before extending this

- Ingestion targets a small bundled sample corpus by default; scaling to the full transcript archive
  means pointing `TRANSCRIPT_SOURCE_URL` at a real source and implementing `stage_online()` in
  `scripts/download_transcripts.py` against that source's actual API shape.
- Schema is created via `Base.metadata.create_all` (`scripts/init_db.py`), not Alembic migrations —
  fine for this scope, but should be replaced with real migrations before any schema change ships to
  a populated database.
- No auth/RBAC — sessions are anonymous. If this needs to become multi-tenant, `user_metadata` on
  `sessions` is the intended extension point.
- Small local models (3B) sometimes deviate from the exact `<artifact>` tag format the system prompt
  asks for; the parser degrades gracefully (falls back to displaying the raw response) but a larger
  local model or the cloud provider is more reliable for artifact-mode requests.
