import { useCallback } from "react";
import { useSSEStream } from "./useSSEStream";
import { API_URL } from "../lib/api";
import type { SSEEvent } from "../types";

export function useUploadDocument(sessionId: string | null, opts?: { onComplete?: (evt: SSEEvent) => void }) {
  const sse = useSSEStream();
  const upload = useCallback(
    (file: File) => {
      if (!sessionId) return Promise.resolve();
      const form = new FormData();
      form.append("file", file);
      form.append("session_id", sessionId);
      return sse.run(`${API_URL}/documents/upload`, { method: "POST", body: form }, (evt) => {
        if (evt.stage === "Complete") opts?.onComplete?.(evt);
      });
    },
    [sessionId, opts, sse]
  );
  return { ...sse, upload };
}
