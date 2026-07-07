import type { Session } from "../../types";

interface SessionListItemProps {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onRename: () => void;
  onDelete: () => void;
}

export default function SessionListItem({ session, isActive, onSelect, onRename, onDelete }: SessionListItemProps) {
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-3 rounded-xl text-sm mb-1 transition-all flex items-center gap-3 border group ${
        isActive
          ? "bg-blue-50 text-blue-700 border-blue-200 font-medium"
          : "text-gray-600 hover:bg-gray-50 hover:text-gray-900 border-transparent"
      }`}
    >
      <i className={`fa-regular fa-message flex-shrink-0 ${isActive ? "text-blue-600" : "text-gray-400"}`}></i>
      <span className="truncate flex-1">{session.title}</span>
      <span
        onClick={(e) => {
          e.stopPropagation();
          onRename();
        }}
        className="flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-gray-400 hover:text-blue-500 hover:bg-blue-50 transition-all opacity-0 group-hover:opacity-100"
      >
        <i className="fa-solid fa-pen text-xs"></i>
      </span>
      <span
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className="flex-shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 transition-all opacity-0 group-hover:opacity-100"
      >
        <i className="fa-solid fa-trash text-xs"></i>
      </span>
    </button>
  );
}
