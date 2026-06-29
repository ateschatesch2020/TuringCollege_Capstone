import React, { useRef, useEffect } from "react";
import { FlatList, View } from "react-native";
import { Message } from "../../types";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: Message[];
}

export function MessageList({ messages }: Props) {
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    if (messages.length > 0) {
      flatListRef.current?.scrollToEnd({ animated: true });
    }
  }, [messages]);

  return (
    <FlatList
      ref={flatListRef}
      data={messages}
      keyExtractor={(_, index) => String(index)}
      renderItem={({ item }) => <MessageBubble message={item} />}
      contentContainerStyle={{ paddingVertical: 16 }}
      onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
    />
  );
}
