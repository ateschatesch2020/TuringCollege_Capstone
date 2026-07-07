import { useRef, useState } from "react";

interface ComposerProps {
  isStreaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

export default function Composer({ isStreaming, onSend, onStop }: ComposerProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleAction = () => {
    if (isStreaming) {
      onStop();
      return;
    }
    const text = value.trim();
    if (!text) return;
    setValue("");
    onSend(text);
  };

  return (
    <div className="shrink-0 p-4 md:p-6 bg-white border-t border-gray-200 z-20 w-full">
      <div className="max-w-4xl mx-auto relative group">
        <div className="relative flex items-end gap-2 bg-gray-50 border border-gray-200 rounded-2xl p-2 shadow-inner focus-within:bg-white focus-within:shadow-md focus-within:border-blue-300 transition-all">
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleAction();
              }
            }}
            className="flex-1 bg-transparent border-none outline-none text-gray-800 placeholder-gray-400 py-3 px-3 resize-none max-h-32 text-sm md:text-base font-sans"
            placeholder="Write a message..."
          />
          <button
            type="button"
            onClick={handleAction}
            className={`p-3 text-white rounded-xl transition-all shadow-md active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed ${
              isStreaming ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"
            }`}
          >
            <i className={`fa-solid ${isStreaming ? "fa-stop" : "fa-paper-plane"}`}></i>
          </button>
        </div>
      </div>
    </div>
  );
}
