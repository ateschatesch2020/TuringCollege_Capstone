import { useState } from "react";
import { useDocuments } from "../../hooks/useDocuments";
import { useIngestPaths } from "../../hooks/useIngestPaths";
import { formatFileSize, estimateUploadTime } from "../../lib/format";
import type { FileSelectEntry } from "../../types";

interface FileSelectWidgetProps {
  files: FileSelectEntry[];
  sessionId: string;
}

export default function FileSelectWidget({ files, sessionId }: FileSelectWidgetProps) {
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [skippedNotice, setSkippedNotice] = useState<string | null>(null);
  const { documents, refresh } = useDocuments(sessionId);
  const { stage, progress, running, ingest } = useIngestPaths(sessionId, { onComplete: () => refresh() });

  const indexed = new Set(documents);

  const toggle = (path: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const handleUpload = async () => {
    const paths = [...checked];
    const filtered = paths.filter((p) => !indexed.has(p.split(/[/\\]/).pop() ?? p));
    const skipped = paths.length - filtered.length;
    setSkippedNotice(skipped > 0 ? `${skipped} file(s) already indexed, skipping.` : null);
    if (filtered.length === 0) return;
    await ingest(filtered);
  };

  return (
    <div className="border border-blue-200 rounded-xl p-3 mt-2 mb-1 bg-blue-50 text-sm">
      <div className="text-xs font-semibold text-blue-700 mb-2 flex items-center gap-1">
        <i className="fa-solid fa-file-arrow-up"></i> Select files to add to knowledge base
      </div>
      <div className="space-y-0.5">
        {files.map((f) => {
          const isPdf = f.name.toLowerCase().endsWith(".pdf");
          return (
            <label
              key={f.path}
              className={`flex items-center gap-2 py-1 px-1 rounded hover:bg-blue-100 cursor-pointer ${
                isPdf ? "" : "opacity-40"
              }`}
            >
              <input
                type="checkbox"
                disabled={!isPdf}
                title={isPdf ? undefined : "Only PDF files can be uploaded"}
                checked={checked.has(f.path)}
                onChange={() => toggle(f.path)}
              />
              <i className="fa-solid fa-file-pdf text-red-400 text-xs flex-shrink-0"></i>
              <span className="text-xs text-gray-700 truncate flex-1">{f.name}</span>
              <span className="text-xs text-gray-400 flex-shrink-0 ml-2">
                {formatFileSize(f.size_bytes)} · {estimateUploadTime(f.size_bytes)}
              </span>
            </label>
          );
        })}
      </div>
      <div className="mt-2 flex items-center gap-2">
        <button
          onClick={handleUpload}
          disabled={checked.size === 0 || running}
          className="bg-blue-600 text-white text-xs px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <i className="fa-solid fa-upload mr-1"></i> Upload Selected
        </button>
        <span className="text-xs text-gray-400">{running ? `${stage} (${progress}%)` : skippedNotice}</span>
      </div>
    </div>
  );
}
