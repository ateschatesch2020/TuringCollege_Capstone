import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useSessions } from "../hooks/useSessions";
import { useModels } from "../hooks/useModels";
import { useEmbeddingModels } from "../hooks/useEmbeddingModels";
import { USER_ID } from "../lib/api";
import type { EmbeddingModelOption, ModelOption, Session } from "../types";

interface SessionContextValue {
  userId: string;
  currentSessionId: string | null;
  setCurrentSessionId: (id: string | null) => void;
  sessions: Session[];
  models: ModelOption[];
  embeddingModels: EmbeddingModelOption[];
  loadSessions: () => Promise<void>;
  createSession: (title: string, sessionId: string, model: string, embeddingModel: string) => Promise<string>;
  renameSession: (sessionId: string, newTitle: string) => Promise<void>;
  updateSessionModel: (sessionId: string, model: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<boolean>;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [currentSessionId, setCurrentSessionIdState] = useState<string | null>(
    () => localStorage.getItem("activeSession")
  );
  const { sessions, loadSessions, createSession, renameSession, updateSessionModel, deleteSession } = useSessions(USER_ID);
  const models = useModels();
  const embeddingModels = useEmbeddingModels();

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const setCurrentSessionId = (id: string | null) => {
    setCurrentSessionIdState(id);
    if (id) localStorage.setItem("activeSession", id);
    else localStorage.removeItem("activeSession");
  };

  const wrappedDeleteSession = async (sessionId: string) => {
    const ok = await deleteSession(sessionId);
    if (ok && currentSessionId === sessionId) {
      setCurrentSessionId(null);
    }
    return ok;
  };

  return (
    <SessionContext.Provider
      value={{
        userId: USER_ID,
        currentSessionId,
        setCurrentSessionId,
        sessions,
        models,
        embeddingModels,
        loadSessions,
        createSession,
        renameSession,
        updateSessionModel,
        deleteSession: wrappedDeleteSession,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSessionContext(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSessionContext must be used within SessionProvider");
  return ctx;
}
