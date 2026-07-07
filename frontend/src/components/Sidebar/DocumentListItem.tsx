import { iconForFile } from "../../lib/fileTypes";

interface DocumentListItemProps {
  name: string;
  onEvaluate: () => void;
  onDelete: () => void;
}

export default function DocumentListItem({ name, onEvaluate, onDelete }: DocumentListItemProps) {
  return (
    <div className="flex items-center justify-between text-xs text-gray-600 px-2 py-1 rounded-lg hover:bg-gray-50 group">
      <span className="truncate">
        <i className={`fa-solid ${iconForFile(name)} text-red-400 mr-1.5`}></i>
        {name}
      </span>
      <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-all ml-1">
        <button onClick={onEvaluate} className="text-gray-400 hover:text-indigo-500 transition-colors" title="Evaluate">
          <i className="fa-solid fa-chart-bar text-xs"></i>
        </button>
        <button onClick={onDelete} className="text-gray-400 hover:text-red-500 transition-colors" title="Delete">
          <i className="fa-solid fa-trash text-xs"></i>
        </button>
      </div>
    </div>
  );
}
