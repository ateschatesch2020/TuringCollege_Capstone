interface ProgressBarProps {
  progress: number;
  variant?: "plain" | "shimmer";
}

export default function ProgressBar({ progress, variant = "plain" }: ProgressBarProps) {
  return (
    <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
      <div
        className={
          variant === "shimmer"
            ? "h-1.5 rounded-full search-bar-shimmer"
            : "bg-blue-500 h-1.5 rounded-full transition-all duration-300"
        }
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
