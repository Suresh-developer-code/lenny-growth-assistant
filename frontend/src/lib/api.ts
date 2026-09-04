export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Provider = "ollama" | "anthropic";
export type ChatMode = "qa" | "ship30" | "artifact";

export interface SourceRef {
  episode: string;
  guest?: string | null;
  timestamp?: string | null;
  score: number;
}

export interface SessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  sources: SourceRef[];
  provider?: string | null;
  mode: string;
  created_at: string;
}

export interface DependencyStatus {
  name: string;
  ok: boolean;
  detail?: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  dependencies: DependencyStatus[];
}

export async function createSession(title?: string): Promise<SessionSummary> {
  const resp = await fetch(`${API_BASE_URL}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!resp.ok) throw new Error(`Failed to create session: HTTP ${resp.status}`);
  return resp.json();
}

export async function getSession(sessionId: string) {
  const resp = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`);
  if (!resp.ok) throw new Error(`Failed to load session: HTTP ${resp.status}`);
  return resp.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const resp = await fetch(`${API_BASE_URL}/api/health`);
  return resp.json();
}

export interface StreamEvent {
  type: "status" | "sources" | "token" | "artifact" | "error";
  content?: string;
  sources?: SourceRef[];
  artifact_type?: "markdown" | "html";
  title?: string;
}

/**
 * Consumes the /api/chat SSE stream and invokes onEvent for each parsed
 * event. Returns when the server sends [DONE] or the stream ends.
 */
export async function streamChat(
  params: { sessionId: string; message: string; mode: ChatMode; provider?: Provider },
  onEvent: (event: StreamEvent) => void
): Promise<void> {
  const resp = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: params.sessionId,
      message: params.message,
      mode: params.mode,
      provider: params.provider ?? null,
    }),
  });

  if (!resp.ok || !resp.body) {
    const detail = await resp.text().catch(() => "");
    throw new Error(`Chat request failed: HTTP ${resp.status} ${detail}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice("data:".length).trim();
      if (payload === "[DONE]") return;
      try {
        const event = JSON.parse(payload) as StreamEvent;
        onEvent(event);
      } catch {
        // ignore malformed keep-alive lines
      }
    }
  }
}
