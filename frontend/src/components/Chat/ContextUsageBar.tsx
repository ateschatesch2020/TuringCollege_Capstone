interface ContextUsageBarProps {
  percent: number | null;
}

export default function ContextUsageBar({ percent }: ContextUsageBarProps) {
  if (percent == null) return null;
  const color = percent < 50 ? "bg-green-400" : percent < 80 ? "bg-yellow-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-1.5 ml-3">
      <div className="w-16 bg-gray-200 rounded-full h-1 overflow-hidden">
        <div className={`h-1 rounded-full transition-all duration-500 ${color}`} style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs text-gray-400">{percent}% context</span>
    </div>
  );
}
