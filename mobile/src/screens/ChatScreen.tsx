import React, { useEffect } from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import { useNavigation, DrawerActions } from "@react-navigation/native";
import { MessageList } from "../components/chat/MessageList";
import { ChatInput } from "../components/chat/ChatInput";
import { WelcomeScreen } from "../components/chat/WelcomeScreen";
import { useChat } from "../hooks/useChat";
import { Message } from "../types";

interface Props {
  activeSessionId: string | null;
  messages: Message[];
  appendMessage: (msg: Message) => void;
  updateLastAssistantMessage: (content: string) => void;
  onReset: () => void;
}

export function ChatScreen({
  activeSessionId,
  messages,
  appendMessage,
  updateLastAssistantMessage,
  onReset,
}: Props) {
  const navigation = useNavigation();
  const { isStreaming, sendMessage, stopStreaming } = useChat({
    appendMessage,
    updateLastAssistantMessage,
  });

  useEffect(() => {
    navigation.setOptions({
      headerLeft: () => (
        <TouchableOpacity
          onPress={() => navigation.dispatch(DrawerActions.toggleDrawer())}
          className="ml-4 p-1"
        >
          <Text className="text-xl">☰</Text>
        </TouchableOpacity>
      ),
      headerRight: () => (
        <TouchableOpacity
          onPress={confirmReset}
          className="mr-4 px-3 py-1 bg-gray-100 rounded-lg"
        >
          <Text className="text-sm text-gray-600 font-medium">Reset</Text>
        </TouchableOpacity>
      ),
      title: "Travel Assistant",
    });
  }, [navigation]);

  function confirmReset() {
    Alert.alert("Reset Chat", "Clear the current session?", [
      { text: "Cancel", style: "cancel" },
      { text: "Reset", style: "destructive", onPress: onReset },
    ]);
  }

  function handleSend(text: string) {
    if (!activeSessionId) {
      Alert.alert("No Session", "Please create or select a chat session first.");
      return;
    }
    sendMessage(text, activeSessionId);
  }

  return (
    <View className="flex-1 bg-gray-50">
      {messages.length === 0 ? (
        <WelcomeScreen />
      ) : (
        <MessageList messages={messages} />
      )}
      <ChatInput
        onSend={handleSend}
        onStop={stopStreaming}
        isStreaming={isStreaming}
        disabled={!activeSessionId}
      />
    </View>
  );
}
