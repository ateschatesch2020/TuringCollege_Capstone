import React from "react";
import { View, Text, Image } from "react-native";
import { Message } from "../../types";

const IMAGE_REGEX = /!\[([^\]]*)\]\((https?:\/\/[^\)]+)\)/g;

interface Segment {
  type: "text" | "image";
  content: string;
  alt?: string;
}

function parseContent(text: string): Segment[] {
  const segments: Segment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  IMAGE_REGEX.lastIndex = 0;

  while ((match = IMAGE_REGEX.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", content: text.slice(lastIndex, match.index) });
    }
    segments.push({ type: "image", content: match[2], alt: match[1] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    segments.push({ type: "text", content: text.slice(lastIndex) });
  }
  return segments;
}

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";
  const segments = parseContent(message.content);

  return (
    <View className={`flex-row mb-3 px-4 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <View className="w-8 h-8 rounded-full bg-blue-600 items-center justify-center mr-2 mt-1 flex-shrink-0">
          <Text className="text-white text-xs font-bold">AI</Text>
        </View>
      )}
      <View
        className={`rounded-2xl px-4 py-3 max-w-[85%] ${
          isUser
            ? "bg-blue-600 rounded-tr-sm"
            : "bg-white border border-gray-200 rounded-tl-sm"
        }`}
      >
        {segments.map((seg, i) =>
          seg.type === "image" ? (
            <Image
              key={i}
              source={{ uri: seg.content }}
              className="rounded-lg mt-1 mb-2"
              style={{ width: 240, height: 160 }}
              resizeMode="cover"
            />
          ) : (
            <Text
              key={i}
              className={`text-sm leading-5 ${isUser ? "text-white" : "text-gray-800"}`}
            >
              {seg.content}
            </Text>
          )
        )}
        {message.content === "" && (
          <Text className="text-gray-400 text-sm italic">Thinking...</Text>
        )}
      </View>
      {isUser && (
        <View className="w-8 h-8 rounded-full bg-gray-300 items-center justify-center ml-2 mt-1 flex-shrink-0">
          <Text className="text-gray-700 text-xs font-bold">U</Text>
        </View>
      )}
    </View>
  );
}
