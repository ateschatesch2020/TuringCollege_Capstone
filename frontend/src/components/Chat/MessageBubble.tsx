import MessageContent from "./MessageContent.tsx";
import type { ChatMessage } from "../../types";

interface MessageBubbleProps {
  message: ChatMessage;
  sessionId: string;
  thinking?: boolean;
}

export default function MessageBubble({ message, sessionId, thinking }: MessageBubbleProps) {
  const isUser = message.role === "user";

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

  return (
    <div className={`flex gap-4 ${isUser ? "flex-row-reverse" : "flex-row"} group w-full`}>
      {avatar}
      <div className="max-w-[85%] md:max-w-[75%] min-w-0">
        <div className={`text-[15px] leading-relaxed py-3.5 px-5 break-text ${bubbleStyle}`}>
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
      </div>
    </div>
  );
}
