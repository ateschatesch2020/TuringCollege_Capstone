import { useRef, useCallback, useState } from "react";
import { API_URL } from "../lib/api";

async function* streamFetch(url: string, body: unknown, controller: AbortController) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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
}

export function useChatStream() {
  const abortRef = useRef<AbortController | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const streamMessage = useCallback(async function* (sessionId: string, query: string, model?: string) {
    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);
    try {
      yield* streamFetch(`${API_URL}/chat`, { session_id: sessionId, query, model }, controller);
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  const streamRetry = useCallback(async function* (
    sessionId: string,
    turnIndex: number,
    query: string,
    model?: string
  ) {
    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);
    try {
      yield* streamFetch(
        `${API_URL}/chat/retry`,
        { session_id: sessionId, turn_index: turnIndex, query, model },
        controller
      );
    } finally {
      abortRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  const stop = useCallback(() => abortRef.current?.abort(), []);
  return { streamMessage, streamRetry, stop, isStreaming };
}
