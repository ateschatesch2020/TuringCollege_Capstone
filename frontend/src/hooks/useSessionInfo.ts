import { useEffect, useState } from "react";
import { API_URL } from "../lib/api";
import type { Session } from "../types";

export function useSessionInfo(sessionId: string | null) {
  const [sessionInfo, setSessionInfo] = useState<Session | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setSessionInfo(null);
      return;
    }
    (async () => {
      try {
        const res = await fetch(`${API_URL}/sessions/${sessionId}/info`);
        if (!res.ok) {
          setSessionInfo(null);
          return;
        }
        setSessionInfo(await res.json());
      } catch (e) {
        console.error(e);
        setSessionInfo(null);
      }
    })();
  }, [sessionId]);

  return sessionInfo;
}
