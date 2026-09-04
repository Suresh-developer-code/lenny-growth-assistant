"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArtifactState } from "@/hooks/useChatStream";
import { SandboxedIframe } from "./SandboxedIframe";

interface ArtifactViewerProps {
  artifact: ArtifactState | null;
  onClose: () => void;
}

export function ArtifactViewer({ artifact, onClose }: ArtifactViewerProps) {
  if (!artifact) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center text-sm text-muted">
        <p>Generated essays and rendered artifacts will appear here, side by side with the chat.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">Artifact</p>
          <h2 className="font-sans text-sm font-semibold">{artifact.title}</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded border border-hairline px-2 py-1 text-xs text-muted hover:border-pine"
          aria-label="Close artifact panel"
        >
          Close
        </button>
      </div>

      <div className="flex-1 overflow-hidden p-4">
        {artifact.artifactType === "html" ? (
          <SandboxedIframe content={artifact.content} title={artifact.title} />
        ) : (
          <div className="h-full overflow-y-auto rounded-lg border border-hairline bg-white p-6">
            <div className="prose-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{artifact.content}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
