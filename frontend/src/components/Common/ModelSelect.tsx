import type { ModelOption } from "../../types";

interface ModelSelectProps {
  models: ModelOption[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
}

function formatContextLength(contextLength: number | null): string {
  if (contextLength == null) return "";
  if (contextLength % 1000000 === 0) return `${contextLength / 1000000}M`;
  if (contextLength % 1000 === 0) return `${contextLength / 1000}K`;
  return `${contextLength}`;
}

export default function ModelSelect({ models, value, onChange, className }: ModelSelectProps) {
  const frontier = models.filter((m) => m.type === "frontier");
  const openSource = models.filter((m) => m.type === "open_source");

  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={className}>
      <optgroup label="Frontier models">
        {frontier.map((m) => (
          <option key={m.id} value={m.id}>
            {m.label} ({m.provider_name})
            {m.context_length != null ? ` — ${formatContextLength(m.context_length)} context` : ""}
          </option>
        ))}
      </optgroup>
      <optgroup label="Open-source models">
        {openSource.map((m) => (
          <option key={m.id} value={m.id}>
            {m.label}
            {m.size_gb != null ? ` — ~${m.size_gb} GB to self-host` : ""}
            {m.context_length != null ? ` — ${formatContextLength(m.context_length)} context` : ""}
          </option>
        ))}
      </optgroup>
    </select>
  );
}
