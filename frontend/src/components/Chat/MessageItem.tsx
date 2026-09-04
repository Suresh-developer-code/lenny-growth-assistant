"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { DisplayMessage } from "@/hooks/useChatStream";

export function MessageItem({ message }: { message: DisplayMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} mb-6`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-3 ${
          isUser
            ? "bg-pine text-white"
            : message.errored
            ? "border border-rust/40 bg-rust/5 text-ink"
            : message.insufficientContext
            ? "border border-dashed border-hairline bg-white text-ink"
            : "bg-white text-ink border border-hairline"
        }`}
      >
        {message.status && (
          <p className="text-sm text-muted italic" aria-live="polite">
            {message.status}
          </p>
        )}
        {message.content && (
          <div className="prose-content text-[0.95rem]" aria-live={isUser ? undefined : "polite"}>
            {isUser ? (
              <p className="whitespace-pre-wrap font-sans">{message.content}</p>
            ) : (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            )}
          </div>
        )}
      </div>

      {!isUser && message.sources.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5 max-w-[80%]">
          {message.sources.map((s, i) => (
            <button
              key={`${s.episode}-${i}`}
              type="button"
              aria-label={`Source: ${s.episode}${s.guest ? `, guest ${s.guest}` : ""}`}
              title={s.timestamp ? `Timestamp: ${s.timestamp}` : undefined}
              className="rounded-full border border-rust/40 bg-rust/5 px-2.5 py-0.5 text-xs text-rust hover:bg-rust/10"
            >
              {s.episode}
              {s.guest ? ` · ${s.guest}` : ""}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
