import { useEffect, useState } from "react";
import { useSessionContext } from "../../context/SessionContext.tsx";
import FileSearchPanel from "./FileSearchPanel.tsx";
import ModelSelect from "../Common/ModelSelect.tsx";
import EmbeddingModelSelect from "../Common/EmbeddingModelSelect.tsx";

interface NewChatModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (sessionId: string) => void;
}

export default function NewChatModal({ open, onClose, onCreated }: NewChatModalProps) {
  const { createSession, models, embeddingModels } = useSessionContext();
  const [title, setTitle] = useState("");
  const [pendingSessionId, setPendingSessionId] = useState<string>("");
  const [modelId, setModelId] = useState("");
  const [embeddingModelId, setEmbeddingModelId] = useState("");

  useEffect(() => {
    if (open) {
      setPendingSessionId(crypto.randomUUID());
      setTitle("");
    }
  }, [open]);

  useEffect(() => {
    if (open && !modelId && models.length > 0) {
      setModelId(models.find((m) => m.type === "frontier")?.id ?? models[0].id);
    }
  }, [open, modelId, models]);

  useEffect(() => {
    if (open && !embeddingModelId && embeddingModels.length > 0) {
      setEmbeddingModelId(embeddingModels[0].id);
    }
  }, [open, embeddingModelId, embeddingModels]);

  if (!open) return null;

  const handleStartChat = async () => {
    const finalTitle = title.trim() || "New Chat";
    const sessionId = await createSession(finalTitle, pendingSessionId, modelId, embeddingModelId);
    onCreated(sessionId);
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-2xl w-[580px] max-h-[85vh] flex flex-col mx-4">
        <div className="px-6 pt-5 pb-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-800 flex items-center gap-2">
            <i className="fa-solid fa-plus text-blue-600 text-sm"></i> New Chat
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        <div className="px-6 py-4 overflow-y-auto flex-1 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
              Chat Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Q3 Report Analysis"
              className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
              Model
            </label>
            <ModelSelect
              models={models}
              value={modelId}
              onChange={setModelId}
              className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wider mb-1.5">
              Embedding Model
            </label>
            <EmbeddingModelSelect
              embeddingModels={embeddingModels}
              value={embeddingModelId}
              onChange={setEmbeddingModelId}
              className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-400 mt-1">Fixed for this session once chosen — applies to every document uploaded here.</p>
          </div>

          {pendingSessionId && (
            <FileSearchPanel sessionId={pendingSessionId} onSearched={() => {}} embeddingModelId={embeddingModelId} />
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">
            Cancel
          </button>
          <button
            onClick={handleStartChat}
            className="px-5 py-2 bg-blue-600 text-white text-sm rounded-xl hover:bg-blue-700 transition-colors shadow-md shadow-blue-100 active:scale-95"
          >
            <i className="fa-solid fa-comment-dots mr-1.5"></i> Start Chat
          </button>
        </div>
      </div>
    </div>
  );
}
