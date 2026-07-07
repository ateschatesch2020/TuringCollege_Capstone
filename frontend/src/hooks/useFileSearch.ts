import { useCallback } from "react";
import { useSSEStream } from "./useSSEStream";
import { API_URL } from "../lib/api";
import type { SSEEvent } from "../types";

export function useFileSearch() {
  const sse = useSSEStream();
  const search = useCallback(
    (keyword: string, exactMatch: boolean, containsName: boolean, onEvent?: (evt: SSEEvent) => void) => {
      return sse.run(
        `${API_URL}/form/search`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword, exact_match: exactMatch, contains_name: containsName }),
        },
        onEvent
      );
    },
    [sse]
  );
  return { ...sse, search };
}
