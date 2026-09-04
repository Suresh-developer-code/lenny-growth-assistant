"use client";

import { useCallback, useRef, useState } from "react";
import { ChatMode, MessageOut, Provider, SourceRef, streamChat } from "@/lib/api";

export interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: SourceRef[];
  status?: string;
  errored?: boolean;
  insufficientContext?: boolean;
}

export interface ArtifactState {
  artifactType: "markdown" | "html";
  title: string;
  content: string;
}

const NO_CONTEXT_MARKER = "I do not have sufficient information in Lenny's podcast archive";

export function useChatStream(sessionId: string | null) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [artifact, setArtifact] = useState<ArtifactState | null>(null);
  const counter = useRef(0);

  const hydrateFromHistory = useCallback((history: MessageOut[]) => {
    setMessages(
      history
        .filter((m) => m.role !== "system")
        .map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          sources: m.sources,
          insufficientContext: m.content.includes(NO_CONTEXT_MARKER),
        }))
    );
  }, []);

  const send = useCallback(
    async (text: string, mode: ChatMode, provider?: Provider) => {
      if (!sessionId || !text.trim() || isStreaming) return;

      const userMsgId = `local-user-${counter.current++}`;
      const assistantMsgId = `local-assistant-${counter.current++}`;

      setMessages((prev) => [
        ...prev,
        { id: userMsgId, role: "user", content: text, sources: [] },
        { id: assistantMsgId, role: "assistant", content: "", sources: [], status: "Searching the transcript archive..." },
      ]);
      setIsStreaming(true);

      let accumulated = "";

      try {
        await streamChat({ sessionId, message: text, mode, provider }, (event) => {
          if (event.type === "status") {
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantMsgId ? { ...m, status: event.content } : m))
            );
          } else if (event.type === "sources") {
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantMsgId ? { ...m, sources: event.sources ?? [] } : m))
            );
          } else if (event.type === "token") {
            accumulated += event.content ?? "";
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      content: accumulated,
                      status: undefined,
                      insufficientContext: accumulated.includes(NO_CONTEXT_MARKER),
                    }
                  : m
              )
            );
          } else if (event.type === "artifact") {
            setArtifact({
              artifactType: event.artifact_type ?? "markdown",
              title: event.title ?? "Untitled artifact",
              content: event.content ?? "",
            });
            // In artifact mode, keep the chat bubble short — the full body is in the panel.
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId && !accumulated.trim()
                  ? { ...m, content: `I've put together **${event.title}** — see it in the Artifact panel.` }
                  : m
              )
            );
          } else if (event.type === "error") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: event.content ?? "Something went wrong.", status: undefined, errored: true }
                  : m
              )
            );
          }
        });
      } catch (err) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content: err instanceof Error ? err.message : "Request failed.",
                  status: undefined,
                  errored: true,
                }
              : m
          )
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [sessionId, isStreaming]
  );

  return { messages, isStreaming, artifact, send, hydrateFromHistory, setArtifact };
}
