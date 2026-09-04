"use client";

import React, { useMemo } from "react";
import DOMPurify from "dompurify";

interface SandboxedIframeProps {
  content: string;
  title: string;
}

/**
 * Renders untrusted, LLM-generated HTML in an isolated iframe.
 *
 * Security model (see docs/architecture.md §7):
 *  - DOMPurify strips dangerous attributes/vectors before the markup ever
 *    reaches the DOM.
 *  - sandbox="allow-scripts" WITHOUT "allow-same-origin" places the iframe
 *    on a unique opaque origin: scripts can run (so interactive artifacts
 *    work) but cannot read this page's cookies, localStorage, or DOM, and
 *    cannot navigate window.top.
 *  - We intentionally do NOT add allow-same-origin, allow-top-navigation,
 *    or allow-popups.
 */
export const SandboxedIframe: React.FC<SandboxedIframeProps> = ({ content, title }) => {
  const cleanHtml = useMemo(() => {
    return DOMPurify.sanitize(content, {
      WHOLE_DOCUMENT: true,
      ADD_TAGS: ["style", "link"],
      ADD_ATTR: ["target"],
    });
  }, [content]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-hairline bg-white">
      <div className="flex items-center justify-between border-b border-hairline bg-paper px-4 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">Artifact: {title}</span>
        <span className="rounded border border-pine/30 bg-pine/5 px-2 py-0.5 text-xs text-pine" title="Scripts run in an isolated frame with no access to this page's cookies, storage, or DOM.">
          Sandboxed preview
        </span>
      </div>
      <iframe
        title={title}
        srcDoc={cleanHtml}
        sandbox="allow-scripts"
        className="h-full w-full flex-1 border-none"
      />
    </div>
  );
};
