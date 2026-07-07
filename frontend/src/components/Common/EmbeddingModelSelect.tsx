import type { EmbeddingModelOption } from "../../types";

interface EmbeddingModelSelectProps {
  embeddingModels: EmbeddingModelOption[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
}

export default function EmbeddingModelSelect({ embeddingModels, value, onChange, className }: EmbeddingModelSelectProps) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={className}>
      {embeddingModels.map((m) => (
        <option key={m.id} value={m.id}>
          {m.label} ({m.dimensions}d, {m.location === "local" ? "runs locally" : "API"})
        </option>
      ))}
    </select>
  );
}
