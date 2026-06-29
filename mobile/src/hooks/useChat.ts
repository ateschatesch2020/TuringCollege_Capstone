import { useState, useRef, useCallback } from "react";
import { API_URL } from "../constants/api";
import { Message } from "../types";

interface UseChatOptions {
  appendMessage: (msg: Message) => void;
  updateLastAssistantMessage: (content: string) => void;
}

export function useChat({ appendMessage, updateLastAssistantMessage }: UseChatOptions) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (query: string, sessionId: string) => {
      if (!query.trim() || !sessionId) return;

      appendMessage({ role: "user", content: query });
      appendMessage({ role: "assistant", content: "" });
      setIsStreaming(true);
      setStreamingText("");

      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch(`${API_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, query }),
          signal: abortControllerRef.current.signal,
          // Required in React Native for incremental chunk reads
          // @ts-ignore
          reactNative: { textStreaming: true },
        });

        const reader = response.body!.getReader();
        const decoder = new TextDecoder("utf-8");
        let fullText = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          fullText += chunk;
          setStreamingText(fullText);
          updateLastAssistantMessage(fullText);
        }
      } catch (err: any) {
        if (err.name === "AbortError") {
          updateLastAssistantMessage("_Interrupted._");
        } else {
          updateLastAssistantMessage("⚠️ An error occurred.");
        }
      } finally {
        setIsStreaming(false);
        setStreamingText("");
        abortControllerRef.current = null;
      }
    },
    [appendMessage, updateLastAssistantMessage]
  );

  const stopStreaming = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);

  return { isStreaming, streamingText, sendMessage, stopStreaming };
}
