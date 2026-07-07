import { useCallback } from "react";
import { useSSEStream } from "./useSSEStream";
import { API_URL } from "../lib/api";
import type { SSEEvent } from "../types";

export function useEvaluation() {
  const sse = useSSEStream();
  const evaluate = useCallback(
    (
      filename: string,
      sessionId: string,
      numQuestions = 20,
      answerModelId: string,
      judgeModelId: string,
      onEvent?: (evt: SSEEvent) => void
    ) => {
      return sse.run(
        `${API_URL}/evaluate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename,
            num_questions: numQuestions,
            session_id: sessionId,
            answer_model_id: answerModelId,
            judge_model_id: judgeModelId,
          }),
        },
        onEvent
      );
    },
    [sse]
  );
  return { ...sse, evaluate };
}
