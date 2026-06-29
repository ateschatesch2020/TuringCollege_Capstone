import React from "react";
import { View, Text } from "react-native";

export function WelcomeScreen() {
  return (
    <View className="flex-1 items-center justify-center px-8">
      <Text className="text-6xl mb-4">🤖</Text>
      <Text className="text-2xl font-bold text-gray-800 mb-2">Travel Assistant</Text>
      <Text className="text-base text-gray-500 text-center">
        Ask me anything about travel policies, flights, or hotels. I'm here to help!
      </Text>
    </View>
  );
}
