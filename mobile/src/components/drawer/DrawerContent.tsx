import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  FlatList,
  Alert,
  TextInput,
  Modal,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { DrawerContentScrollView } from "@react-navigation/drawer";
import { SessionItem } from "./SessionItem";
import { DocumentItem } from "./DocumentItem";
import { UploadProgressBar } from "../shared/UploadProgressBar";
import { USER_ID } from "../../constants/api";

interface Props {
  drawerProps: any;
  sessions: any[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onCreateSession: (title: string) => void;
  onRenameSession: (id: string, title: string) => void;
  onDeleteSession: (id: string) => void;
  documents: string[];
  isUploading: boolean;
  uploadStage: string;
  uploadProgress: number;
  onUpload: () => void;
  onDeleteDocument: (filename: string) => void;
}

export function DrawerContent({
  drawerProps,
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateSession,
  onRenameSession,
  onDeleteSession,
  documents,
  isUploading,
  uploadStage,
  uploadProgress,
  onUpload,
  onDeleteDocument,
}: Props) {
  const [newChatModalVisible, setNewChatModalVisible] = useState(false);
  const [newChatTitle, setNewChatTitle] = useState("");

  function handleCreateChat() {
    const trimmed = newChatTitle.trim();
    if (!trimmed) return;
    onCreateSession(trimmed);
    setNewChatTitle("");
    setNewChatModalVisible(false);
    drawerProps.navigation.closeDrawer();
  }

  return (
    <View className="flex-1 bg-gray-50">
      {/* Header */}
      <View className="px-4 pt-12 pb-4 border-b border-gray-200">
        <Text className="text-xl font-bold text-blue-700">✈️ Travel Assistant</Text>
        <View className="flex-row items-center mt-1">
          <View className="w-2 h-2 rounded-full bg-green-500 mr-2" />
          <Text className="text-xs text-gray-500">System Ready</Text>
        </View>
      </View>

      <ScrollView className="flex-1" showsVerticalScrollIndicator={false}>
        {/* New Chat button */}
        <TouchableOpacity
          onPress={() => setNewChatModalVisible(true)}
          className="flex-row items-center mx-4 mt-4 mb-2 px-4 py-3 bg-blue-600 rounded-xl"
        >
          <Text className="text-white font-semibold text-sm flex-1">+ New Chat</Text>
        </TouchableOpacity>

        {/* Sessions */}
        <Text className="text-xs font-semibold text-gray-400 uppercase px-4 mb-1 mt-3">
          Chats
        </Text>
        {sessions.length === 0 ? (
          <Text className="text-xs text-gray-400 px-6 py-2">No sessions yet</Text>
        ) : (
          sessions.map((s) => (
            <SessionItem
              key={s.session_id}
              session={s}
              isActive={s.session_id === activeSessionId}
              onSelect={() => {
                onSelectSession(s.session_id);
                drawerProps.navigation.closeDrawer();
              }}
              onRename={(title) => onRenameSession(s.session_id, title)}
              onDelete={() => onDeleteSession(s.session_id)}
            />
          ))
        )}

        {/* Documents */}
        <Text className="text-xs font-semibold text-gray-400 uppercase px-4 mb-1 mt-4">
          Documents
        </Text>
        <TouchableOpacity
          onPress={onUpload}
          disabled={isUploading}
          className={`flex-row items-center mx-4 mb-2 px-4 py-2 rounded-xl border ${
            isUploading ? "border-gray-200 bg-gray-100" : "border-blue-300 bg-blue-50"
          }`}
        >
          <Text className="text-blue-600 text-sm font-medium">
            {isUploading ? "Uploading..." : "📎 Upload PDF"}
          </Text>
        </TouchableOpacity>

        {isUploading && (
          <UploadProgressBar stage={uploadStage} progress={uploadProgress} />
        )}

        {documents.length === 0 ? (
          <Text className="text-xs text-gray-400 px-6 py-1">No documents uploaded</Text>
        ) : (
          documents.map((doc) => (
            <DocumentItem
              key={doc}
              filename={doc}
              onDelete={() => onDeleteDocument(doc)}
            />
          ))
        )}
      </ScrollView>

      {/* User footer */}
      <View className="border-t border-gray-200 px-4 py-4 flex-row items-center">
        <View className="w-9 h-9 rounded-full bg-blue-600 items-center justify-center mr-3">
          <Text className="text-white font-bold text-sm">
            {USER_ID.charAt(0).toUpperCase()}
          </Text>
        </View>
        <View>
          <Text className="text-sm font-medium text-gray-800">{USER_ID}</Text>
          <View className="flex-row items-center">
            <View className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1" />
            <Text className="text-xs text-gray-500">Online</Text>
          </View>
        </View>
      </View>

      {/* New Chat Modal */}
      <Modal
        visible={newChatModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setNewChatModalVisible(false)}
      >
        <View className="flex-1 bg-black/50 justify-center px-8">
          <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
            <View className="bg-white rounded-2xl p-6">
              <Text className="text-base font-semibold text-gray-800 mb-4">
                New Chat
              </Text>
              <TextInput
                className="border border-gray-300 rounded-xl px-4 py-2 text-gray-800 text-sm mb-4"
                placeholder="Chat title..."
                value={newChatTitle}
                onChangeText={setNewChatTitle}
                autoFocus
                onSubmitEditing={handleCreateChat}
              />
              <View className="flex-row justify-end gap-3">
                <TouchableOpacity
                  onPress={() => {
                    setNewChatModalVisible(false);
                    setNewChatTitle("");
                  }}
                  className="px-4 py-2 rounded-xl bg-gray-100"
                >
                  <Text className="text-gray-600 text-sm font-medium">Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={handleCreateChat}
                  className="px-4 py-2 rounded-xl bg-blue-600"
                >
                  <Text className="text-white text-sm font-medium">Create</Text>
                </TouchableOpacity>
              </View>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>
    </View>
  );
}
