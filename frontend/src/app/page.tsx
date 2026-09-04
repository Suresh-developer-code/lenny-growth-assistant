"use client";

import { useEffect, useState } from "react";
import { createSession, getHealth, getSession, HealthResponse, Provider } from "@/lib/api";
import { useChatStream } from "@/hooks/useChatStream";
import { ChatPane } from "@/components/Chat/ChatPane";
import { ArtifactViewer } from "@/components/Artifact/ArtifactViewer";

const SESSION_STORAGE_KEY = "lenny-session-id";

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [provider, setProvider] = useState<Provider>("ollama");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [mobileTab, setMobileTab] = useState<"chat" | "artifact">("chat");
  const [initError, setInitError] = useState<string | null>(null);

  const { messages, isStreaming, artifact, send, hydrateFromHistory, setArtifact } = useChatStream(sessionId);

  // Bootstrap: reuse an existing session id (survives reload) or create one.
  useEffect(() => {
    const bootstrap = async () => {
      try {
        const existing =
          typeof window !== "undefined" ? window.sessionStorage.getItem(SESSION_STORAGE_KEY) : null;

        if (existing) {
          try {
            const detail = await getSession(existing);
            setSessionId(existing);
            hydrateFromHistory(detail.messages);
            return;
          } catch {
            // stale/invalid session id — fall through and create a fresh one
          }
        }

        const created = await createSession("New session");
        setSessionId(created.id);
        if (typeof window !== "undefined") {
          window.sessionStorage.setItem(SESSION_STORAGE_KEY, created.id);
        }
      } catch (err) {
        setInitError(
          err instanceof Error
            ? `Could not reach the backend API. ${err.message}`
            : "Could not reach the backend API."
        );
      }
    };
    bootstrap();
  }, [hydrateFromHistory]);

  // Poll health so provider availability is visible before the user hits send.
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const h = await getHealth();
        if (!cancelled) setHealth(h);
      } catch {
        if (!cancelled) setHealth(null);
      }
    };
    poll();
    const interval = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (artifact) setMobileTab("artifact");
  }, [artifact]);

  if (initError) {
    return (
      <div className="flex h-screen items-center justify-center p-6 text-center">
        <div className="max-w-sm rounded border border-rust/40 bg-rust/5 p-6">
          <p className="mb-2 font-semibold">Backend unavailable</p>
          <p className="text-sm text-muted">{initError}</p>
          <p className="mt-3 text-xs text-muted">
            Check that the API is running (see README) and NEXT_PUBLIC_API_URL points at it.
          </p>
        </div>
      </div>
    );
  }

  return (
    <main className="flex h-screen flex-col">
      {/* Mobile tab switcher */}
      <div className="flex border-b border-hairline sm:hidden">
        {(["chat", "artifact"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setMobileTab(tab)}
            className={`flex-1 py-2 text-sm ${mobileTab === tab ? "border-b-2 border-pine font-medium" : "text-muted"}`}
          >
            {tab === "chat" ? "Chat" : "Artifact"}
          </button>
        ))}
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className={`h-full flex-1 sm:w-3/5 ${mobileTab === "artifact" ? "hidden sm:block" : "block"}`}>
          <ChatPane
            messages={messages}
            isStreaming={isStreaming}
            provider={provider}
            onProviderChange={setProvider}
            health={health}
            onSend={(text, mode) => send(text, mode, provider)}
          />
        </div>
        <div
          className={`h-full border-hairline sm:block sm:w-2/5 sm:border-l ${
            mobileTab === "chat" ? "hidden" : "block w-full"
          }`}
        >
          <ArtifactViewer artifact={artifact} onClose={() => setArtifact(null)} />
        </div>
      </div>
    </main>
  );
}
