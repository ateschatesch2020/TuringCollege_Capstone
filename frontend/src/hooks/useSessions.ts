import { useCallback, useState } from "react";
import { API_URL } from "../lib/api";
import type { Session } from "../types";

export function useSessions(userId: string) {
  const [sessions, setSessions] = useState<Session[]>([]);

  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/sessions/${userId}`);
      const data = await res.json();
      setSessions(data.sessions ?? []);
    } catch (e) {
      console.error(e);
    }
  }, [userId]);

  const createSession = useCallback(
    async (title: string, sessionId: string, model: string, embeddingModel: string): Promise<string> => {
      const res = await fetch(`${API_URL}/sessions/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, title, session_id: sessionId, model, embedding_model: embeddingModel }),
      });
      const data = await res.json();
      return data.session_id as string;
    },
    [userId]
  );

  const renameSession = useCallback(
    async (sessionId: string, newTitle: string) => {
      const res = await fetch(`${API_URL}/sessions/${sessionId}/rename`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle }),
      });
      if (res.ok) await loadSessions();
    },
    [loadSessions]
  );

  const updateSessionModel = useCallback(
    async (sessionId: string, model: string) => {
      const res = await fetch(`${API_URL}/sessions/${sessionId}/model`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
      });
      if (res.ok) await loadSessions();
    },
    [loadSessions]
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      const res = await fetch(`${API_URL}/sessions/${sessionId}`, { method: "DELETE" });
      if (res.ok) await loadSessions();
      return res.ok;
    },
    [loadSessions]
  );

  return { sessions, loadSessions, createSession, renameSession, updateSessionModel, deleteSession };
}
