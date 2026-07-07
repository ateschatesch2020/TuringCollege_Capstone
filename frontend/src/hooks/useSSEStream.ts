import { useCallback, useRef, useState } from "react";
import { streamSSE } from "../lib/sse";
import type { SSEEvent } from "../types";

export function useSSEStream() {
  const [stage, setStage] = useState("");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(
    async (url: string, init: RequestInit, onEvent?: (evt: SSEEvent) => void) => {
      setError(null);
      setProgress(0);
      setStage("");
      setRunning(true);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        for await (const evt of streamSSE(url, { ...init, signal: controller.signal })) {
          if (evt.error) {
            setError(evt.error);
            onEvent?.(evt);
            break;
          }
          if (typeof evt.progress === "number") setProgress(evt.progress);
          if (evt.stage) setStage(evt.stage);
          onEvent?.(evt);
        }
      } catch (e) {
        if (e instanceof Error && e.name !== "AbortError") setError(e.message);
        else if (e instanceof Error && e.name === "AbortError") setStage("Cancelled");
      } finally {
        setRunning(false);
        abortRef.current = null;
      }
    },
    []
  );

  const abort = useCallback(() => abortRef.current?.abort(), []);
  return { stage, progress, error, running, run, abort };
}
