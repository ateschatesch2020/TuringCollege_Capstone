import { useEffect, useRef, useState } from "react";
import { useSessionContext } from "../context/SessionContext.tsx";
import { DocumentsProvider } from "../context/DocumentsContext.tsx";
import { useChatStream } from "../hooks/useChatStream";
import { useTokenUsage } from "../hooks/useTokenUsage";
import { API_URL } from "../lib/api";
import Sidebar from "../components/Sidebar/Sidebar.tsx";
import ChatHeader from "../components/Chat/ChatHeader.tsx";
import ChatContainer from "../components/Chat/ChatContainer.tsx";
import Composer from "../components/Chat/Composer.tsx";
import NewChatModal from "../components/NewChatModal/NewChatModal.tsx";
import type { ChatMessage } from "../types";

export default function ChatPage() {
  const { currentSessionId, setCurrentSessionId, loadSessions } = useSessionContext();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { streamMessage, stop, isStreaming } = useChatStream();
  const { percent, refresh: refreshTokenUsage } = useTokenUsage();
  const sendStartedRef = useRef(false);

  useEffect(() => {
    sendStartedRef.current = false;
    if (!currentSessionId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        await loadSessions();
        const res = await fetch(`${API_URL}/history/${currentSessionId}`);
        const data = await res.json();
        if (!cancelled && !sendStartedRef.current) setMessages(data.messages ?? []);
        await refreshTokenUsage(currentSessionId);
      } catch (e) {
        console.error(e);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const t = setTimeout(() => el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }), 50);
    return () => clearTimeout(t);
  }, [messages]);

  const handleSend = async (text: string) => {
    if (!currentSessionId) {
      alert("Please start a new chat first.");
      return;
    }
    sendStartedRef.current = true;
    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);
    try {
      for await (const fullText of streamMessage(currentSessionId, text)) {
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = { role: "assistant", content: fullText };
          return copy;
        });
      }
      await refreshTokenUsage(currentSessionId);
    } catch (err) {
      const msg = err instanceof Error && err.name === "AbortError" ? "Interrupted." : "An error occurred.";
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: "assistant", content: msg };
        return copy;
      });
      if (!(err instanceof Error && err.name === "AbortError")) console.error(err);
    }
  };

  return (
    <DocumentsProvider sessionId={currentSessionId}>
      <Sidebar onNewChat={() => setModalOpen(true)} />
      <div className="flex-1 flex flex-col h-full bg-gray-50/50 min-w-0 relative">
        <ChatHeader percent={percent} onReset={() => setCurrentSessionId(null)} />
        <ChatContainer
          ref={scrollRef}
          sessionId={currentSessionId}
          messages={messages}
          streamingLastMessage={isStreaming}
        />
        <Composer isStreaming={isStreaming} onSend={handleSend} onStop={stop} />
      </div>
      <NewChatModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={(sessionId) => {
          setModalOpen(false);
          setCurrentSessionId(sessionId);
        }}
      />
    </DocumentsProvider>
  );
}
