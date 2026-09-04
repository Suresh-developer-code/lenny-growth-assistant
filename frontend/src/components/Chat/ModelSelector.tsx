"use client";

import { Provider } from "@/lib/api";

interface ModelSelectorProps {
  provider: Provider;
  onChange: (provider: Provider) => void;
  ollamaOk: boolean | null;
  anthropicOk: boolean | null;
}

export function ModelSelector({ provider, onChange, ollamaOk, anthropicOk }: ModelSelectorProps) {
  const options: { value: Provider; label: string; ok: boolean | null; reason: string }[] = [
    { value: "ollama", label: "Local · Ollama", ok: ollamaOk, reason: "Ollama not reachable at localhost:11434" },
    { value: "anthropic", label: "Cloud · Claude", ok: anthropicOk, reason: "No Anthropic API key configured" },
  ];

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-muted">Model</span>
      <select
        value={provider}
        onChange={(e) => onChange(e.target.value as Provider)}
        className="rounded border border-hairline bg-white px-2 py-1 text-ink"
        aria-label="Select model provider"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.ok === false}>
            {opt.label}
            {opt.ok === false ? " (unavailable)" : ""}
          </option>
        ))}
      </select>
      <span
        className="inline-block h-2 w-2 rounded-full"
        style={{ backgroundColor: options.find((o) => o.value === provider)?.ok === false ? "#C6501E" : "#3B6E5E" }}
        aria-hidden="true"
      />
      {options.find((o) => o.value === provider)?.ok === false && (
        <span className="text-xs text-rust">{options.find((o) => o.value === provider)?.reason}</span>
      )}
    </div>
  );
}
