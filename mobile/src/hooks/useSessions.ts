import { useState, useCallback } from "react";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { API_URL, USER_ID } from "../constants/api";
import { Session, Message } from "../types";

const ACTIVE_SESSION_KEY = "activeSession";

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);

  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/sessions/${USER_ID}`);
      const data = await res.json();
      setSessions(data.sessions ?? []);
    } catch {
      setSessions([]);
    }
  }, []);

  const loadHistory = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`${API_URL}/history/${sessionId}`);
      const data = await res.json();
      setMessages(data.messages ?? []);
    } catch {
      setMessages([]);
    }
  }, []);

  const selectSession = useCallback(
    async (sessionId: string) => {
      setActiveSessionId(sessionId);
      await AsyncStorage.setItem(ACTIVE_SESSION_KEY, sessionId);
      await loadHistory(sessionId);
    },
    [loadHistory]
  );

  const createSession = useCallback(
    async (title: string) => {
      const res = await fetch(`${API_URL}/sessions/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: USER_ID, title }),
      });
      const data = await res.json();
      await loadSessions();
      await selectSession(data.session_id);
      return data.session_id as string;
    },
    [loadSessions, selectSession]
  );

  const renameSession = useCallback(
    async (sessionId: string, title: string) => {
      await fetch(`${API_URL}/sessions/${sessionId}/rename`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      await loadSessions();
    },
    [loadSessions]
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      await fetch(`${API_URL}/sessions/${sessionId}`, { method: "DELETE" });
      await loadSessions();
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
        await AsyncStorage.removeItem(ACTIVE_SESSION_KEY);
      }
    },
    [activeSessionId, loadSessions]
  );

  const restoreSession = useCallback(async () => {
    const saved = await AsyncStorage.getItem(ACTIVE_SESSION_KEY);
    if (saved) {
      setActiveSessionId(saved);
      await loadHistory(saved);
    }
  }, [loadHistory]);

  const appendMessage = useCallback((msg: Message) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const updateLastAssistantMessage = useCallback((content: string) => {
    setMessages((prev) => {
      const copy = [...prev];
      if (copy.length > 0 && copy[copy.length - 1].role === "assistant") {
        copy[copy.length - 1] = { role: "assistant", content };
      }
      return copy;
    });
  }, []);

  return {
    sessions,
    activeSessionId,
    messages,
    loadSessions,
    selectSession,
    createSession,
    renameSession,
    deleteSession,
    restoreSession,
    appendMessage,
    updateLastAssistantMessage,
    setMessages,
  };
}
