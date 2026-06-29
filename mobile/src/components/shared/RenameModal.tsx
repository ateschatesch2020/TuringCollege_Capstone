import React, { useState } from "react";
import {
  Modal,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from "react-native";

interface Props {
  visible: boolean;
  initialValue: string;
  onConfirm: (newTitle: string) => void;
  onCancel: () => void;
}

export function RenameModal({ visible, initialValue, onConfirm, onCancel }: Props) {
  const [value, setValue] = useState(initialValue);

  function handleConfirm() {
    const trimmed = value.trim();
    if (trimmed) onConfirm(trimmed);
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View className="flex-1 bg-black/50 justify-center px-8">
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
          <View className="bg-white rounded-2xl p-6">
            <Text className="text-base font-semibold text-gray-800 mb-4">
              Rename Session
            </Text>
            <TextInput
              className="border border-gray-300 rounded-xl px-4 py-2 text-gray-800 text-sm mb-4"
              value={value}
              onChangeText={setValue}
              autoFocus
              onSubmitEditing={handleConfirm}
            />
            <View className="flex-row justify-end gap-3">
              <TouchableOpacity
                onPress={onCancel}
                className="px-4 py-2 rounded-xl bg-gray-100"
              >
                <Text className="text-gray-600 text-sm font-medium">Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                onPress={handleConfirm}
                className="px-4 py-2 rounded-xl bg-blue-600"
              >
                <Text className="text-white text-sm font-medium">Rename</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}
