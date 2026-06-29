import React, { useState } from "react";
import {
  View,
  TextInput,
  TouchableOpacity,
  Text,
  KeyboardAvoidingView,
  Platform,
} from "react-native";

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled: boolean;
}

export function ChatInput({ onSend, onStop, isStreaming, disabled }: Props) {
  const [text, setText] = useState("");
  const [inputHeight, setInputHeight] = useState(44);

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setText("");
    setInputHeight(44);
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      keyboardVerticalOffset={88}
    >
      <View className="flex-row items-end px-4 py-3 border-t border-gray-200 bg-white">
        <TextInput
          className="flex-1 bg-gray-100 rounded-2xl px-4 py-2 text-gray-800 text-sm mr-3"
          style={{ height: Math.min(Math.max(inputHeight, 44), 120) }}
          placeholder="Ask about travel policies, flights, hotels..."
          placeholderTextColor="#9ca3af"
          value={text}
          onChangeText={setText}
          multiline
          onContentSizeChange={(e) =>
            setInputHeight(e.nativeEvent.contentSize.height + 16)
          }
          onSubmitEditing={handleSend}
          returnKeyType="send"
          blurOnSubmit={false}
          editable={!disabled}
        />
        <TouchableOpacity
          onPress={isStreaming ? onStop : handleSend}
          className={`w-11 h-11 rounded-full items-center justify-center ${
            isStreaming ? "bg-red-500" : text.trim() ? "bg-blue-600" : "bg-gray-300"
          }`}
          disabled={!isStreaming && (!text.trim() || disabled)}
        >
          <Text className="text-white text-lg">{isStreaming ? "⏹" : "➤"}</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}
