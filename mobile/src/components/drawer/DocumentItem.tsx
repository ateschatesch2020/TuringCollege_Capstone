import React from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";

interface Props {
  filename: string;
  onDelete: () => void;
}

export function DocumentItem({ filename, onDelete }: Props) {
  function confirmDelete() {
    Alert.alert("Remove Document", `Remove "${filename}" from the index?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Remove", style: "destructive", onPress: onDelete },
    ]);
  }

  return (
    <View className="flex-row items-center px-4 py-2 mx-2">
      <Text className="text-sm mr-2">📄</Text>
      <Text className="flex-1 text-xs text-gray-600" numberOfLines={1}>
        {filename}
      </Text>
      <TouchableOpacity onPress={confirmDelete} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
        <Text className="text-gray-400 text-xs">🗑️</Text>
      </TouchableOpacity>
    </View>
  );
}
