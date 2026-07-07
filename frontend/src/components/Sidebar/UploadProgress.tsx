interface UploadProgressProps {
  visible: boolean;
  stage: string;
  progress: number;
  onCancel: () => void;
}

export default function UploadProgress({ visible, stage, progress, onCancel }: UploadProgressProps) {
  if (!visible) return null;
  return (
    <div className="mt-2 mb-1 px-1">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-gray-400 truncate flex-1">{stage}</p>
        <button onClick={onCancel} className="text-xs text-red-400 hover:text-red-600 ml-2 transition-colors" title="Cancel upload">
          <i className="fa-solid fa-xmark"></i>
        </button>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1.5">
        <div className="bg-blue-500 h-1.5 rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
