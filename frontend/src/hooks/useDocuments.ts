import { useCallback, useEffect, useState } from "react";
import { API_URL } from "../lib/api";

export function useDocuments(sessionId: string | null) {
  const [documents, setDocuments] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!sessionId) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/documents?session_id=${encodeURIComponent(sessionId)}`);
      if (!res.ok) {
        setDocuments([]);
        return;
      }
      const data = await res.json();
      setDocuments(data.documents ?? []);
    } catch (e) {
      console.error(e);
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const deleteDocument = useCallback(
    async (filename: string) => {
      if (!sessionId) return;
      const res = await fetch(
        `${API_URL}/documents/${encodeURIComponent(filename)}?session_id=${encodeURIComponent(sessionId)}`,
        { method: "DELETE" }
      );
      await refresh();
      return res.ok;
    },
    [sessionId, refresh]
  );

  return { documents, loading, refresh, deleteDocument };
}
