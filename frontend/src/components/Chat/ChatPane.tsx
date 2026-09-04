"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ChatMode, HealthResponse, Provider } from "@/lib/api";
import { DisplayMessage } from "@/hooks/useChatStream";
import { MessageItem } from "./MessageItem";
import { ModelSelector } from "./ModelSelector";

const EXAMPLE_QUESTIONS = [
  "What does Casey Winters say about growth loops vs funnels?",
  "How should I structure onboarding for a new PM, per Julie Zhuo?",
  "What's Elena Verna's take on usage-based vs seat-based pricing?",
  "Turn what we discussed into a Ship 30 for 30 essay.",
];

interface ChatPaneProps {
  messages: DisplayMessage[];
  isStreaming: boolean;
  provider: Provider;
  onProviderChange: (p: Provider) => void;
  health: HealthResponse | null;
  onSend: (text: string, mode: ChatMode) => void;
}

export function ChatPane({ messages, isStreaming, provider, onProviderChange, health, onSend }: ChatPaneProps) {
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<ChatMode>("qa");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const ollamaOk = health?.dependencies.find((d) => d.name === "provider:ollama")?.ok ?? null;
  const anthropicOk = health?.dependencies.find((d) => d.name === "provider:anthropic")?.ok ?? null;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSend(input, mode);
    setInput("");
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
        <h1 className="font-sans text-base font-semibold">The Lenny Growth Assistant</h1>
        <ModelSelector provider={provider} onChange={onProviderChange} ollamaOk={ollamaOk} anthropicOk={anthropicOk} />
      </div>

      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="mx-auto max-w-md text-center">
            <p className="mb-4 text-sm text-muted">Ask something grounded in Lenny&apos;s Podcast archive:</p>
            <div className="flex flex-col gap-2">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => onSend(q, q.startsWith("Turn") ? "ship30" : "qa")}
                  className="rounded border border-hairline bg-white px-3 py-2 text-left text-sm hover:border-pine"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => <MessageItem key={m.id} message={m} />)
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-hairline p-4">
        <div className="mb-2 flex gap-2 text-xs">
          {(["qa", "ship30", "artifact"] as ChatMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded-full px-3 py-1 ${
                mode === m ? "bg-pine text-white" : "border border-hairline bg-white text-muted"
              }`}
            >
              {m === "qa" ? "Ask" : m === "ship30" ? "Ship 30 essay" : "Build artifact"}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e as unknown as FormEvent);
              }
            }}
            placeholder="Ask a product or growth question..."
            rows={2}
            className="max-h-40 flex-1 resize-none rounded border border-hairline bg-white px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="rounded bg-pine px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
