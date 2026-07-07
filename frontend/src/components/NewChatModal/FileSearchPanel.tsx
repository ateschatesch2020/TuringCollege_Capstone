import { useRef, useState } from "react";
import { useFileSearch } from "../../hooks/useFileSearch";
import { formatRemaining } from "../../lib/format";
import ProgressBar from "../Common/ProgressBar.tsx";
import MessageContent from "../Chat/MessageContent.tsx";
import type { SSEEvent } from "../../types";

interface FileSearchPanelProps {
  sessionId: string;
  onSearched: () => void;
  embeddingModelId?: string;
}

export default function FileSearchPanel({ sessionId, onSearched, embeddingModelId }: FileSearchPanelProps) {
  const [keyword, setKeyword] = useState("");
  const [exactMatch, setExactMatch] = useState(false);
  const [containsName, setContainsName] = useState(true);
  const [label, setLabel] = useState("Searching...");
  const [result, setResult] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const { progress, running, search } = useFileSearch();

  const emaRef = useRef<number | null>(null);
  const lastPctRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number | null>(null);

  const handleSearch = async () => {
    const kw = keyword.trim();
    if (!kw) return;
    if (!exactMatch && !containsName) {
      alert("Please select at least one search mode (Exact match or Contains in name).");
      return;
    }
    setResult(null);
    setFailed(false);
    setLabel("Searching...");
    emaRef.current = null;
    lastPctRef.current = null;
    lastTimeRef.current = null;

    const onEvent = (evt: SSEEvent) => {
      if (evt.stage === "Counting files...") {
        setLabel("Counting files...");
      } else if (typeof evt.progress === "number" && evt.progress < 100) {
        const now = performance.now();
        if (lastTimeRef.current !== null && evt.progress > (lastPctRef.current ?? 0)) {
          const dtSeconds = (now - lastTimeRef.current) / 1000;
          const instantRate = (evt.progress - (lastPctRef.current ?? 0)) / dtSeconds;
          emaRef.current = emaRef.current === null ? instantRate : 0.1 * instantRate + 0.9 * emaRef.current;
        }
        lastPctRef.current = evt.progress;
        lastTimeRef.current = now;
        setLabel(
          emaRef.current && emaRef.current > 0
            ? `Searching... (${formatRemaining(Math.round((100 - evt.progress) / emaRef.current))})`
            : "Searching..."
        );
      }
      if (evt.stage === "Complete" && typeof evt.result === "string") {
        setResult(evt.result);
        onSearched();
      }
    };

    try {
      await search(kw, exactMatch, containsName, onEvent);
    } catch {
      setFailed(true);
    }
  };

  return (
    <div className="border border-gray-200 rounded-xl p-4 bg-gray-50 space-y-3">
      <p className="text-xs font-semibold text-gray-600 tracking-wider flex items-center gap-1.5">
        <i className="fa-solid fa-magnifying-glass text-blue-500"></i>
        Find Files to Upload
        <span className="font-normal text-gray-400 ml-1">(optional)</span>
      </p>
      <div className="flex gap-2">
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Keyword..."
          className="flex-1 border border-gray-200 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
        />
        <button
          onClick={handleSearch}
          disabled={running}
          className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center gap-1.5"
        >
          <i className="fa-solid fa-search text-xs"></i> Search
        </button>
      </div>
      <div className="flex gap-5 text-sm text-gray-600">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={exactMatch}
            onChange={(e) => setExactMatch(e.target.checked)}
            className="rounded accent-blue-600"
          />
          <span>Exact match</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={containsName}
            onChange={(e) => setContainsName(e.target.checked)}
            className="rounded accent-blue-600"
          />
          <span>Contains in name</span>
        </label>
      </div>

      {running && (
        <div className="py-1">
          <p className="text-xs text-gray-400 mb-1">{label}</p>
          <ProgressBar progress={progress} variant="shimmer" />
        </div>
      )}

      {failed && <p className="text-xs text-red-400">Search failed. Is the backend running?</p>}

      {result && (
        <div className="overflow-x-auto min-w-0 break-words text-sm">
          <MessageContent text={result} sessionId={sessionId} embeddingModelId={embeddingModelId} />
        </div>
      )}
    </div>
  );
}
