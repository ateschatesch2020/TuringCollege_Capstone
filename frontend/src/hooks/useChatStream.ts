import { useRef, useCallback, useState } from "react";
import { API_URL } from "../lib/api";

export function useChatStream() {
  const abortRef = useRef<AbortController | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const streamMessage = useCallback(async function* (sessionId: string, query: string, model?: string) {
    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, query, model }),
        signal: controller.signal,
      });
      const reader = res.body!.getReader();
      const decoder = new TextDecoder("utf-8");
      let fullText = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        fullText += decoder.decode(value, { stream: true });
        yield fullText;
      }
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  const stop = useCallback(() => abortRef.current?.abort(), []);
  return { streamMessage, stop, isStreaming };
}
