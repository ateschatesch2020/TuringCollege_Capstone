import { useSessionContext } from "../../context/SessionContext.tsx";
import SessionListItem from "./SessionListItem.tsx";

export default function SessionList() {
  const { sessions, currentSessionId, setCurrentSessionId, renameSession, deleteSession } = useSessionContext();

  if (sessions.length === 0) {
    return <div className="text-center text-gray-400 text-xs mt-4">No sessions created yet.</div>;
  }

  return (
    <div className="flex-1 overflow-y-auto px-3 space-y-1">
      {sessions.map((session) => (
        <SessionListItem
          key={session.session_id}
          session={session}
          isActive={session.session_id === currentSessionId}
          onSelect={() => setCurrentSessionId(session.session_id)}
          onRename={() => {
            const newTitle = prompt("New title:", session.title);
            if (!newTitle || newTitle.trim() === session.title) return;
            renameSession(session.session_id, newTitle.trim());
          }}
          onDelete={() => deleteSession(session.session_id)}
        />
      ))}
    </div>
  );
}
