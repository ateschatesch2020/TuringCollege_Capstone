import { useState, useCallback } from "react";
import * as DocumentPicker from "expo-document-picker";
import { API_URL } from "../constants/api";

export function useDocuments() {
  const [documents, setDocuments] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStage, setUploadStage] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);

  const loadDocuments = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/documents`);
      const data = await res.json();
      setDocuments(data.documents ?? []);
    } catch {
      setDocuments([]);
    }
  }, []);

  const uploadDocument = useCallback(async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: "application/pdf",
    });
    if (result.canceled) return;

    const asset = result.assets[0];
    const formData = new FormData();
    formData.append("file", {
      uri: asset.uri,
      name: asset.name,
      type: asset.mimeType ?? "application/pdf",
    } as any);

    setIsUploading(true);
    setUploadProgress(0);
    setUploadStage("Starting...");

    try {
      const response = await fetch(`${API_URL}/documents/upload`, {
        method: "POST",
        body: formData,
        // @ts-ignore
        reactNative: { textStreaming: true },
      });

      const reader = response.body!.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          let evt: any;
          try {
            evt = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }
          if (evt.error) {
            setUploadStage(`Error: ${evt.error}`);
            return;
          }
          setUploadStage(evt.stage ?? "");
          setUploadProgress(evt.progress ?? 0);
          if (evt.stage === "Complete") {
            await loadDocuments();
          }
        }
      }
    } finally {
      setIsUploading(false);
    }
  }, [loadDocuments]);

  const deleteDocument = useCallback(
    async (filename: string) => {
      await fetch(`${API_URL}/documents/${encodeURIComponent(filename)}`, {
        method: "DELETE",
      });
      await loadDocuments();
    },
    [loadDocuments]
  );

  return {
    documents,
    isUploading,
    uploadStage,
    uploadProgress,
    loadDocuments,
    uploadDocument,
    deleteDocument,
  };
}
