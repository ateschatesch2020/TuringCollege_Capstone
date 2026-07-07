import { createContext, useContext, type ReactNode } from "react";
import { useDocuments } from "../hooks/useDocuments";

interface DocumentsContextValue {
  documents: string[];
  loading: boolean;
  refresh: () => Promise<void>;
  deleteDocument: (filename: string) => Promise<boolean | undefined>;
}

const DocumentsContext = createContext<DocumentsContextValue | null>(null);

export function DocumentsProvider({ sessionId, children }: { sessionId: string | null; children: ReactNode }) {
  const value = useDocuments(sessionId);
  return <DocumentsContext.Provider value={value}>{children}</DocumentsContext.Provider>;
}

export function useDocumentsContext(): DocumentsContextValue {
  const ctx = useContext(DocumentsContext);
  if (!ctx) throw new Error("useDocumentsContext must be used within DocumentsProvider");
  return ctx;
}
