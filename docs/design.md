# Design — The Lenny Growth Assistant

## 1. Principles

1. **The transcript archive is the product, not the chat window.** Every design decision should make sourcing *more* visible than a typical chatbot, not less — citations are first-class UI, not a footnote.
2. **Two kinds of output, two panes.** Conversational answers (short, exploratory) and generated artifacts (long, keep-able) have different lifecycles. They should never compete for the same space.
3. **Trust is legible.** Which model answered, whether an answer is grounded or a "not found," and what an artifact is allowed to do — all visible without a click.
4. **Quiet by default, opinionated in one place.** The chat surface stays restrained (it's a work tool used for long sessions); the one deliberate visual choice is the citation/source treatment, which uses a distinct warm accent so sourced claims are easy to visually scan.

## 2. Visual system

- **Color**: `#1B1F23` (near-black text/ink), `#FAFAF7` (warm paper background — a working document, not a dashboard), `#3B6E5E` (deep pine — primary actions, provider-active state), `#C6501E` (rust — citation markers only, used nowhere else so it stays meaningful), `#E7E2D6` (hairline borders/dividers), `#6B7280` (secondary text/timestamps).
- **Type**: `Source Serif 4` for chat prose and generated essays (a reading typeface, since this product's output is meant to be read and republished, not skimmed like a SaaS UI) paired with `Inter` for UI chrome — inputs, buttons, labels, code. Two families, clearly distinct roles: serif = content, sans = interface.
- **Layout**: two-column, left-weighted (60/40 chat/artifact) on desktop, collapsing to tabs on mobile. Left-aligned prose throughout (no centered marketing-style blocks) — this is a work tool.

```
Desktop (>1024px)                       Mobile (<640px)
┌───────────────┬───────────────┐       ┌─────────────────┐
│ Session list ▾ │  Artifact      │       │  [Chat][Artifact]│  <- tabs
│───────────────│  Viewer        │       │─────────────────│
│ chat messages  │  (collapsible) │       │  chat OR         │
│ ...            │                │       │  artifact,        │
│ [citations]    │  [safe-render  │       │  full width       │
│───────────────│   badge]       │       │─────────────────│
│ input + model  │                │       │ input + model    │
│ selector       │                │       │ selector          │
└───────────────┴───────────────┘       └─────────────────┘
```

## 3. Key interaction states

- **Empty session**: instead of a generic "ask me anything," the empty state surfaces 3–4 real example questions drawn from the ingested corpus's actual episode titles, so the first interaction demonstrates grounding immediately.
- **Retrieving**: a single inline status line ("Searching the transcript archive…") streamed as the first SSE event — not a spinner overlay, so the user isn't blocked from reading earlier turns.
- **Streaming answer**: tokens append live; citation chips render as soon as the `sources` metadata event arrives, ahead of the full answer finishing, so trust signal appears early.
- **Insufficient context**: visually distinct message style (dashed border, muted tone) rather than looking like a normal answer — a "no" should not look like a confident "yes" formatted the same way.
- **Artifact generated**: right pane auto-opens (desktop) or a toast + tab-switch affordance appears (mobile); artifact header always shows type, title, and a "Sandboxed preview" badge with a tooltip explaining what that means in plain language.
- **Provider unavailable**: the model selector itself shows a disabled state with inline reason ("Ollama not reachable at localhost:11434") rather than only failing after the user sends a message.
- **Error**: errors speak in the interface's voice — "That request couldn't be completed: the local model didn't respond in time. Try again, or switch to Claude (cloud)." Never a raw stack trace client-side.

## 4. Responsive behavior

- **≥1024px**: fixed two-pane layout, artifact pane resizable/collapsible via a drag handle.
- **640–1024px**: artifact pane becomes an overlay drawer triggered from a header icon, chat stays full width underneath.
- **<640px**: tab switcher (Chat / Artifact) replaces the two-pane layout entirely; only one is mounted at a time to keep the DOM light on mobile.
- Composer input uses `textarea` with auto-grow capped at ~6 lines before scrolling internally, so the input never pushes the message list off-screen on small viewports.

## 5. Accessibility

- All interactive elements reachable by keyboard; visible focus ring (`2px solid #3B6E5E`, never `outline: none` without replacement).
- Streaming text updates use `aria-live="polite"` on the message container so screen readers announce new content without interrupting.
- Citation chips are real `<button>` elements (not `<div onClick>`), each with an `aria-label` naming the episode and guest, not just a visual mark.
- Color is never the only signal: the "insufficient context" state uses a dashed border + icon + text label, not color alone; provider status uses text ("Local · Ollama") alongside a colored dot.
- Contrast: body text `#1B1F23` on `#FAFAF7` and UI text on white both exceed WCAG AA at their respective sizes.
- `prefers-reduced-motion` respected — the only intentional motion (message stream-in, artifact pane open) is disabled/instant for users who request it.

## 6. Reasoning for restraint

The one deliberate flourish is the rust-colored citation system, because in a grounded-answer product, "where did this come from" is the single fact users most need to scan quickly — everything else (chat bubbles, buttons, the artifact chrome) stays quiet Inter/serif typography with no gradients, card-shadow kits, or decorative icons, so the citation treatment doesn't have to compete for attention.
