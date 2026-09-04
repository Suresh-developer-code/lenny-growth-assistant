# PRD — The Lenny Growth Assistant

## 1. Forward Deployment Discovery Brief

### 1.1 Primary user & job to be done
**Primary user:** A growth PM or founder who follows *Lenny's Podcast* but doesn't have time to listen to 200+ hours of episodes. They are usually mid-decision on something concrete — a pricing experiment, an onboarding redesign, a PLG motion — and want to know "what have credible operators actually said about this?"

**Job to be done:** "When I'm about to make a growth/product decision, let me pull specific, attributed tactics from people who've done this before, in minutes, and let me turn that into something I can publish or share with my team."

**Pain removed:** Podcasts are a poor reference format — you can't skim, search, or cite them. The assistant turns an unstructured audio archive into a queryable, citable knowledge base, and turns raw answers into shareable written artifacts (an essay, a one-pager) without a separate writing tool.

### 1.2 Success metrics
We define one primary and two supporting metrics:

| Metric | Target | Why it matters |
|---|---|---|
| **Retrieval citation accuracy** (primary) | ≥ 90% of grounded answers cite a chunk that a human reviewer agrees actually supports the claim | This is a RAG product — if citations are wrong, the product is untrustworthy regardless of how fluent the prose is |
| Local inference time-to-first-token | < 4s on the reference 8B Ollama model | The mandatory local demo has to feel usable, not just "technically working" |
| Artifact render safety | 0 successful script escapes from the sandboxed iframe in adversarial testing | Rendering LLM-generated HTML is the single riskiest surface in the app |

Operationally, we'd also track "% of sessions with a follow-up question" as a proxy for whether the assistant is actually useful enough to have a conversation with, rather than a one-shot search box.

### 1.3 Assumptions (brief was incomplete)
Because the assignment specifies frameworks and constraints but not exact data or scale, we assumed:

1. **Transcript corpus**: no bulk, licensed transcript dump is available in this environment (no live network access to third-party transcript archives). We built a real ingestion pipeline (`scripts/download_transcripts.py` + `scripts/ingest.py`) designed against Lenny's public "Newsletter/Podcast transcripts" GitHub-style repository layout (one text/markdown file per episode with a front-matter block for guest/title/date), and shipped a small set of representative sample transcripts so the whole pipeline — chunk → embed → store → retrieve — is demonstrable end-to-end without requiring the evaluator to first go find and license a large dataset. The ingestion script is written to point at a real repo URL via `TRANSCRIPT_SOURCE_URL` and will scale to the full archive unmodified.
2. **"Local model that runs comfortably"**: we standardized on `llama3.2:3b` as the default Ollama demo model (comfortable on a 16GB laptop) with `llama3.1:8b`/`mistral:7b` as documented upgrades, rather than assuming the evaluator has a GPU.
3. **Single tenant, no auth**: the brief doesn't mention multi-tenant auth, so we scoped user identity to a lightweight `user_id` header/cookie rather than building a full auth system — this is called out explicitly as excluded (see below).
4. **"Session" = conversation, not "user account."** Sessions are anonymous by default; `user_metadata` (JSONB) is a free-form field a real deployment would populate from SSO.
5. **Citation format**: we chose `[Episode: Guest — Topic/Timestamp]` inline citations plus a structured `sources` array on every assistant message, so the frontend can render both human-readable citations and a machine-checkable source list.
6. **"Artifact" scope**: limited to Markdown documents and self-contained HTML/CSS (+ optional vanilla JS) snippets, per spec — no arbitrary file downloads, no external script tags.

### 1.4 Scope choices

**In scope:**
- Grounded Q&A over transcript chunks with citations and an explicit "not enough context" fallback.
- Ship 30 for 30 essay-generation skill as a distinct, structured tool (not a one-off prompt).
- Markdown + HTML/CSS artifact generation with a sandboxed, side-by-side viewer.
- Dual model layer: Ollama (default/required) and Anthropic Claude (cloud), switchable per-request without redeploying.
- Session + message + artifact persistence in Postgres, with `pgvector` for retrieval.
- Docker Compose one-command bring-up, health checks, structured logs, graceful degradation.

**Explicitly excluded (and why):**
- **Full auth/RBAC** — out of scope for this brief (that's the *other* assignment in this workspace). We use a minimal session-scoped identity instead of building login/roles here, to keep focus on the RAG/agent/artifact problem this brief is actually about.
- **Real-time multi-user collaboration** on a single session — no requirement for it, adds significant complexity (CRDTs/locking) for no stated user benefit.
- **Automatic re-ingestion / scheduled crawling** — we implemented a manual/CLI-triggered ingestion job, not a cron/scheduler, since freshness SLAs weren't specified.
- **Fine-tuning or model training** — retrieval + prompting is sufficient and keeps the system provider-agnostic.
- **Full observability stack (Prometheus/Grafana)** — we use structured JSON logs + a `/api/health` probe instead of standing up a metrics stack, which would be disproportionate for a take-home.

### 1.5 Risks & trade-offs

| Risk | Mitigation / trade-off accepted |
|---|---|
| **Hallucination** | Strict system prompt requiring citations for every factual claim; similarity threshold below which the model is instructed to say it doesn't know; we accept this reduces recall (some true-but-borderline answers get refused) in exchange for precision. |
| **Local model quality** | 3B models reason worse than cloud frontier models, especially on multi-hop synthesis (e.g., "compare what 3 different guests said about X"). We surface the active provider in the UI so users calibrate trust accordingly, and default retrieval-heavy tasks work reasonably well on small models because the model mostly needs to summarize retrieved text, not reason from scratch. |
| **Latency** | Streaming (SSE) response so perceived latency is low even if total generation is slow; retrieval runs before generation starts and its status is streamed as a discrete event. |
| **Cost (cloud path)** | Config-gated — cloud provider is opt-in via `DEFAULT_LLM_PROVIDER`/request header, never silently invoked. |
| **Data leakage / prompt injection via transcripts** | Transcript content is treated as data, not instructions — the system prompt explicitly tells the model retrieved chunks are reference material only, and we never interpolate retrieved text into anywhere except a clearly-delimited context block. |
| **Unsafe artifact rendering (XSS)** | Generated HTML is rendered in a sandboxed `<iframe srcdoc>` with `sandbox="allow-scripts"` and **no** `allow-same-origin`, plus DOMPurify pre-sanitization. This means iframe scripts can run (needed for interactive artifacts like calculators) but cannot read cookies, localStorage, or the parent DOM, and cannot navigate the top-level page. Documented fully in `architecture.md §7`. |
| **Local Ollama unavailable** | `/api/health` reports Ollama status separately from DB status; chat requests fail with a structured 503 + actionable message rather than hanging or crashing, and the frontend surfaces a clear "local model unavailable, switch provider" state. |

## 2. User flows

### 2.1 Grounded Q&A
1. User opens the app → a new session is created (`POST /api/sessions`).
2. User asks a product/growth question.
3. Backend embeds the query, retrieves top-K chunks from `pgvector`, and streams a grounded answer with inline citations + a `sources` payload.
4. User asks a follow-up — full session history is included in context.
5. If retrieval similarity is below threshold, the assistant explicitly says the archive doesn't cover it, and does not fabricate an answer.

### 2.2 Ship 30 for 30 essay
1. User asks the assistant to turn the current thread (or a fresh topic) into an essay ("write this up Ship 30 style").
2. The **Ship30Writer** skill runs its own retrieval pass if needed, builds a structured prompt encoding hook/structure/formatting/takeaway rules, and generates a ~1,250-word Markdown artifact.
3. Artifact appears in the right-hand Artifact Viewer; the chat pane gets a short "here's your essay →" acknowledgment, not the full essay dumped into the chat bubble.

### 2.3 Artifact generation (HTML/CSS)
1. User asks for a rendered snippet ("make me a one-pager / a calculator / a comparison table").
2. Assistant returns a fenced `<artifact type="html">` block.
3. Frontend detects the tag, sanitizes it, and mounts it in the sandboxed iframe beside the chat.

## 3. Acceptance criteria

- [ ] A new chat session can be created and persists across a page reload (via session ID in URL).
- [ ] Each session's message history is isolated from other sessions.
- [ ] Every grounded answer includes at least one citation *or* an explicit "insufficient context" statement — never neither.
- [ ] Switching the provider dropdown between "Ollama (local)" and "Claude (cloud)" changes which backend actually serves the next message, without a restart.
- [ ] `/api/health` returns per-dependency status (db, vector index, ollama, cloud key present) with correct HTTP status codes when a dependency is down.
- [ ] The Ship 30 skill produces a Markdown artifact between ~1,100–1,400 words with H2/H3 headers, bold anchors, and a closing checklist/framework.
- [ ] An HTML artifact containing a `<script>` that attempts `document.cookie` or `window.parent.postMessage` cannot access the parent page (verified in manual test plan).
- [ ] `docker compose up` brings up db + backend + frontend with no manual steps beyond copying `.env.example` → `.env`.

## 4. Implementation plan (as delivered)

1. Discovery docs (this file, `architecture.md`, `design.md`).
2. Postgres schema + `pgvector` + SQLAlchemy models.
3. Ingestion pipeline + sample transcript corpus.
4. Provider abstraction (Ollama + Anthropic) behind one interface.
5. Retriever + grounded system prompt.
6. Ship 30 skill + artifact-generation skill.
7. FastAPI routes (sessions, chat/streaming, health) + structured logging + error handling.
8. Next.js frontend: chat pane, model selector, sandboxed artifact viewer.
9. Docker Compose, `.env.example`, tests, README, this PRD, agent transcripts.
