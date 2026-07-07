import { useCallback } from "react";
import { useSSEStream } from "./useSSEStream";
import { API_URL } from "../lib/api";
import type { SSEEvent } from "../types";

export function useIngestPaths(sessionId: string | null, opts?: { onComplete?: (evt: SSEEvent) => void }) {
  const sse = useSSEStream();
  const ingest = useCallback(
    (paths: string[], embeddingModelId?: string) => {
      if (!sessionId) return Promise.resolve();
      return sse.run(
        `${API_URL}/documents/ingest-paths`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paths, session_id: sessionId, embedding_model_id: embeddingModelId }),
        },
        (evt) => {
          if (evt.stage === "Complete") opts?.onComplete?.(evt);
        }
      );
    },
    [sessionId, opts, sse]
  );
  return { ...sse, ingest };
}
