import { useCallback } from "react";
import { useSSEStream } from "./useSSEStream";
import { API_URL } from "../lib/api";
import type { SSEEvent } from "../types";

export function useEvaluation() {
  const sse = useSSEStream();
  const evaluate = useCallback(
    (filename: string, sessionId: string, numQuestions = 20, onEvent?: (evt: SSEEvent) => void) => {
      return sse.run(
        `${API_URL}/evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename, num_questions: numQuestions, session_id: sessionId }),
        },
        onEvent
      );
    },
    [sse]
  );
  return { ...sse, evaluate };
}
