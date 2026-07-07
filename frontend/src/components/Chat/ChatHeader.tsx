import ContextUsageBar from "./ContextUsageBar.tsx";

interface ChatHeaderProps {
  percent: number | null;
  onReset: () => void;
}

export default function ChatHeader({ percent, onReset }: ChatHeaderProps) {
  return (
    <div className="h-16 shrink-0 border-b border-gray-200 flex items-center justify-between px-6 bg-white/80 backdrop-blur-md z-10">
      <div className="flex items-center gap-2 text-gray-500">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
        <span className="text-xs font-medium">System Ready</span>
        <ContextUsageBar percent={percent} />
      </div>
      <button
        onClick={onReset}
        className="text-xs text-gray-400 hover:text-red-500 transition-colors bg-gray-100 px-3 py-1.5 rounded-full"
        title="Reset Session"
      >
        <i className="fa-solid fa-power-off mr-1"></i> Reset
      </button>
    </div>
  );
}
