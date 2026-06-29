import React from "react";
import { View, Text } from "react-native";

interface Props {
  stage: string;
  progress: number;
}

export function UploadProgressBar({ stage, progress }: Props) {
  return (
    <View className="mx-4 mb-3">
      <Text className="text-xs text-gray-500 mb-1">{stage}</Text>
      <View className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <View
          className="h-full bg-blue-500 rounded-full"
          style={{ width: `${progress}%` }}
        />
      </View>
    </View>
  );
}
