import { forwardRef } from "react";
import MessageBubble from "./MessageBubble.tsx";
import WelcomeScreen from "./WelcomeScreen.tsx";
import EmptyChatNotice from "./EmptyChatNotice.tsx";
import type { ChatMessage } from "../../types";

interface ChatContainerProps {
  sessionId: string | null;
  messages: ChatMessage[];
  streamingLastMessage: boolean;
  onRetry?: (turnIndex: number, newText: string) => void;
}

const ChatContainer = forwardRef<HTMLDivElement, ChatContainerProps>(function ChatContainer(
  { sessionId, messages, streamingLastMessage, onRetry },
  ref
) {
  let userTurnCount = 0;
  return (
    <div ref={ref} className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 scroll-smooth w-full">
      {!sessionId ? (
        <WelcomeScreen />
      ) : messages.length === 0 ? (
        <EmptyChatNotice />
      ) : (
        messages.map((message, i) => {
          const turnIndex = message.role === "user" ? userTurnCount++ : undefined;
          return (
            <MessageBubble
              key={i}
              message={message}
              sessionId={sessionId}
              thinking={streamingLastMessage && i === messages.length - 1 && message.content === ""}
              turnIndex={turnIndex}
              onRetry={onRetry}
            />
          );
        })
      )}
    </div>
  );
});

export default ChatContainer;
