import React, { useEffect } from "react";
import { createDrawerNavigator } from "@react-navigation/drawer";
import { DrawerContent } from "../components/drawer/DrawerContent";
import { ChatScreen } from "../screens/ChatScreen";
import { useSessions } from "../hooks/useSessions";
import { useDocuments } from "../hooks/useDocuments";

const Drawer = createDrawerNavigator();

export function AppNavigator() {
  const {
    sessions,
    activeSessionId,
    messages,
    loadSessions,
    selectSession,
    createSession,
    renameSession,
    deleteSession,
    restoreSession,
    appendMessage,
    updateLastAssistantMessage,
    setMessages,
  } = useSessions();

  const {
    documents,
    isUploading,
    uploadStage,
    uploadProgress,
    loadDocuments,
    uploadDocument,
    deleteDocument,
  } = useDocuments();

  useEffect(() => {
    async function init() {
      await Promise.all([loadSessions(), loadDocuments(), restoreSession()]);
    }
    init();
  }, []);

  function handleReset() {
    setMessages([]);
  }

  return (
    <Drawer.Navigator
      drawerContent={(props) => (
        <DrawerContent
          drawerProps={props}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={selectSession}
          onCreateSession={createSession}
          onRenameSession={renameSession}
          onDeleteSession={deleteSession}
          documents={documents}
          isUploading={isUploading}
          uploadStage={uploadStage}
          uploadProgress={uploadProgress}
          onUpload={uploadDocument}
          onDeleteDocument={deleteDocument}
        />
      )}
      screenOptions={{
        drawerType: "slide",
        overlayColor: "rgba(0,0,0,0.4)",
        headerStyle: { backgroundColor: "#fff" },
        headerShadowVisible: true,
      }}
    >
      <Drawer.Screen name="Chat">
        {() => (
          <ChatScreen
            activeSessionId={activeSessionId}
            messages={messages}
            appendMessage={appendMessage}
            updateLastAssistantMessage={updateLastAssistantMessage}
            onReset={handleReset}
          />
        )}
      </Drawer.Screen>
    </Drawer.Navigator>
  );
}
