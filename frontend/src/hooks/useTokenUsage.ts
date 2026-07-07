import { useCallback, useState } from "react";
import { API_URL } from "../lib/api";

export function useTokenUsage() {
  const [percent, setPercent] = useState<number | null>(null);

  const refresh = useCallback(async (sessionId: string | null) => {
    if (!sessionId) return;
    try {
      const res = await fetch(`${API_URL}/sessions/${sessionId}/token-usage`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.percent == null) return;
      setPercent(data.percent);
    } catch {
      /* ignore */
    }
  }, []);

  return { percent, refresh };
}
