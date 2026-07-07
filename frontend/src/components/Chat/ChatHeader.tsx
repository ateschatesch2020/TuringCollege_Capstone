import ContextUsageBar from "./ContextUsageBar.tsx";
import ModelSelect from "../Common/ModelSelect.tsx";
import type { EmbeddingModelOption, ModelOption } from "../../types";

interface ChatHeaderProps {
  percent: number | null;
  onReset: () => void;
  model?: string;
  models: ModelOption[];
  onModelChange: (id: string) => void;
  embeddingModelId?: string;
  embeddingModels: EmbeddingModelOption[];
}

export default function ChatHeader({ percent, onReset, model, models, onModelChange, embeddingModelId, embeddingModels }: ChatHeaderProps) {
  const embeddingInfo = embeddingModels.find((m) => m.id === embeddingModelId);
  return (
    <div className="h-16 shrink-0 border-b border-gray-200 flex items-center justify-between px-6 bg-white/80 backdrop-blur-md z-10">
      <div className="flex items-center gap-2 text-gray-500">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
        <span className="text-xs font-medium">System Ready</span>
        <ContextUsageBar percent={percent} />
      </div>
      <div className="flex items-center gap-3">
        {embeddingInfo && (
          <span
            className="text-xs text-gray-500 bg-gray-100 px-3 py-1.5 rounded-full"
            title="Embedding model used for this session's documents (fixed at creation)"
          >
            <i className="fa-solid fa-database mr-1"></i> {embeddingInfo.label} ({embeddingInfo.dimensions}d)
          </span>
        )}
        {model && (
          <ModelSelect
            models={models}
            value={model}
            onChange={onModelChange}
            className="text-xs border border-gray-200 rounded-full px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        )}
        <button
          onClick={onReset}
          className="text-xs text-gray-400 hover:text-red-500 transition-colors bg-gray-100 px-3 py-1.5 rounded-full"
          title="Reset Session"
        >
          <i className="fa-solid fa-power-off mr-1"></i> Reset
        </button>
      </div>
    </div>
  );
}
