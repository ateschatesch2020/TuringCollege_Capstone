import { useDocumentsContext } from "../../context/DocumentsContext.tsx";
import { useSessionContext } from "../../context/SessionContext.tsx";
import DocumentListItem from "./DocumentListItem.tsx";

export default function DocumentList() {
  const { currentSessionId } = useSessionContext();
  const { documents, loading, deleteDocument } = useDocumentsContext();

  if (!currentSessionId) {
    return <p className="text-xs text-gray-400 px-2">Select or start a chat to see its documents.</p>;
  }
  if (loading && documents.length === 0) {
    return <p className="text-xs text-gray-400 px-2">Loading...</p>;
  }
  if (documents.length === 0) {
    return <p className="text-xs text-gray-400 px-2">No documents uploaded.</p>;
  }

  return (
    <div className="space-y-1 max-h-36 overflow-y-auto">
      {documents.map((name) => (
        <DocumentListItem
          key={name}
          name={name}
          onEvaluate={() => {
            const sessionParam = currentSessionId ? `&session_id=${encodeURIComponent(currentSessionId)}` : "";
            window.open(`/evaluate?file=${encodeURIComponent(name)}${sessionParam}`, "_blank");
          }}
          onDelete={async () => {
            if (!confirm(`Remove "${name}" from the knowledge base?`)) return;
            await deleteDocument(name);
          }}
        />
      ))}
    </div>
  );
}
