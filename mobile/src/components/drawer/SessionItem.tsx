import React, { useState } from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import { Session } from "../../types";
import { RenameModal } from "../shared/RenameModal";

interface Props {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onRename: (newTitle: string) => void;
  onDelete: () => void;
}

export function SessionItem({ session, isActive, onSelect, onRename, onDelete }: Props) {
  const [renameVisible, setRenameVisible] = useState(false);

  function confirmDelete() {
    Alert.alert("Delete Session", `Delete "${session.title}"?`, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: onDelete },
    ]);
  }

  return (
    <>
      <TouchableOpacity
        onPress={onSelect}
        className={`flex-row items-center px-4 py-3 mx-2 mb-1 rounded-xl ${
          isActive ? "bg-blue-100" : "bg-transparent"
        }`}
      >
        <Text className="text-base mr-2">💬</Text>
        <Text
          className={`flex-1 text-sm font-medium ${
            isActive ? "text-blue-700" : "text-gray-700"
          }`}
          numberOfLines={1}
        >
          {session.title}
        </Text>
        <View className="flex-row gap-1">
          <TouchableOpacity
            onPress={() => setRenameVisible(true)}
            className="p-1"
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 4 }}
          >
            <Text className="text-gray-400 text-xs">✏️</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={confirmDelete}
            className="p-1"
            hitSlop={{ top: 8, bottom: 8, left: 4, right: 8 }}
          >
            <Text className="text-gray-400 text-xs">🗑️</Text>
          </TouchableOpacity>
        </View>
      </TouchableOpacity>

      <RenameModal
        visible={renameVisible}
        initialValue={session.title}
        onConfirm={(newTitle) => {
          setRenameVisible(false);
          onRename(newTitle);
        }}
        onCancel={() => setRenameVisible(false)}
      />
    </>
  );
}
