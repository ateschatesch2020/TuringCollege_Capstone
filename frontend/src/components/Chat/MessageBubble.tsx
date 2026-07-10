import { useState } from "react";
import type { MouseEvent } from "react";
import MessageContent from "./MessageContent.tsx";
import type { ChatMessage } from "../../types";

interface MessageBubbleProps {
  message: ChatMessage;
  sessionId: string;
  thinking?: boolean;
  turnIndex?: number;
  onRetry?: (turnIndex: number, newText: string) => void;
}

export default function MessageBubble({ message, sessionId, thinking, turnIndex, onRetry }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const canRetry = isUser && !!onRetry && turnIndex !== undefined;

  const [menuPos, setMenuPos] = useState<{ x: number; y: number } | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(message.content);

  const avatar = isUser ? (
    <div className="w-9 h-9 rounded-full bg-blue-600 flex-shrink-0 flex items-center justify-center text-xs font-bold text-white shadow-sm ring-2 ring-white">
      U
    </div>
  ) : (
    <div className="w-9 h-9 rounded-full bg-white flex-shrink-0 flex items-center justify-center text-xs text-blue-600 shadow-sm border border-gray-200">
      <i className="fa-solid fa-robot text-lg"></i>
    </div>
  );

  const bubbleStyle = isUser
    ? "bg-blue-600 text-white rounded-2xl rounded-tr-none shadow-md shadow-blue-100"
    : "bg-white text-gray-800 border border-gray-200 rounded-2xl rounded-tl-none shadow-sm";

  const handleContextMenu = (e: MouseEvent<HTMLDivElement>) => {
    if (!canRetry) return;
    e.preventDefault();
    setMenuPos({ x: e.clientX, y: e.clientY });
  };

  const startEdit = () => {
    setDraft(message.content);
    setEditing(true);
    setMenuPos(null);
  };

  const cancelEdit = () => {
    setEditing(false);
    setDraft(message.content);
  };

  const submitEdit = () => {
    const text = draft.trim();
    if (!text || turnIndex === undefined || !onRetry) return;
    setEditing(false);
    onRetry(turnIndex, text);
  };

  return (
    <div className={`flex gap-4 ${isUser ? "flex-row-reverse" : "flex-row"} group w-full`}>
      {avatar}
      <div className="max-w-[85%] md:max-w-[75%] min-w-0">
        {editing ? (
          <div className="flex flex-col gap-2 items-end">
            <textarea
              autoFocus
              rows={2}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  e.preventDefault();
                  cancelEdit();
                } else if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submitEdit();
                }
              }}
              className="w-full text-[15px] leading-relaxed py-3 px-4 rounded-2xl border border-blue-300 bg-white text-gray-800 outline-none resize-none shadow-sm"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={cancelEdit}
                className="px-3 py-1 text-xs rounded-lg text-gray-600 hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={submitEdit}
                className="px-3 py-1 text-xs rounded-lg bg-blue-600 text-white hover:bg-blue-700"
              >
                Save &amp; Retry
              </button>
            </div>
          </div>
        ) : (
          <div
            onContextMenu={handleContextMenu}
            className={`text-[15px] leading-relaxed py-3.5 px-5 break-text ${bubbleStyle}`}
          >
            {isUser ? (
              message.content
            ) : thinking ? (
              <span>
                <i className="fa-solid fa-circle-notch fa-spin"></i> Thinking...
              </span>
            ) : (
              <MessageContent text={message.content} sessionId={sessionId} />
            )}
          </div>
        )}
      </div>
      {menuPos && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setMenuPos(null)} onContextMenu={(e) => e.preventDefault()} />
          <div
            className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 text-sm min-w-[120px]"
            style={{ top: menuPos.y, left: menuPos.x }}
          >
            <button
              type="button"
              onClick={startEdit}
              className="block w-full text-left px-4 py-2 hover:bg-gray-100 text-gray-700"
            >
              <i className="fa-solid fa-rotate-right mr-2"></i>Retry
            </button>
          </div>
        </>
      )}
    </div>
  );
}
