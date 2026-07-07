import { forwardRef } from "react";
import MessageBubble from "./MessageBubble.tsx";
import WelcomeScreen from "./WelcomeScreen.tsx";
import EmptyChatNotice from "./EmptyChatNotice.tsx";
import type { ChatMessage } from "../../types";

interface ChatContainerProps {
  sessionId: string | null;
  messages: ChatMessage[];
  streamingLastMessage: boolean;
}

const ChatContainer = forwardRef<HTMLDivElement, ChatContainerProps>(function ChatContainer(
  { sessionId, messages, streamingLastMessage },
  ref
) {
  return (
    <div ref={ref} className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 scroll-smooth w-full">
      {!sessionId ? (
        <WelcomeScreen />
      ) : messages.length === 0 ? (
        <EmptyChatNotice />
      ) : (
        messages.map((message, i) => (
          <MessageBubble
            key={i}
            message={message}
            sessionId={sessionId}
            thinking={streamingLastMessage && i === messages.length - 1 && message.content === ""}
          />
        ))
      )}
    </div>
  );
});

export default ChatContainer;
