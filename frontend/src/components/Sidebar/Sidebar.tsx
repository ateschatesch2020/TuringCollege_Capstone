import { useRef } from "react";
import { useSessionContext } from "../../context/SessionContext.tsx";
import { useDocumentsContext } from "../../context/DocumentsContext.tsx";
import { useUploadDocument } from "../../hooks/useUploadDocument";
import { SUPPORTED_EXTENSIONS } from "../../lib/fileTypes";
import SessionList from "./SessionList.tsx";
import DocumentList from "./DocumentList.tsx";
import UploadProgress from "./UploadProgress.tsx";
import UserFooter from "./UserFooter.tsx";

interface SidebarProps {
  onNewChat: () => void;
}

export default function Sidebar({ onNewChat }: SidebarProps) {
  const { currentSessionId } = useSessionContext();
  const { refresh } = useDocumentsContext();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { stage, progress, running, upload, abort } = useUploadDocument(currentSessionId, {
    onComplete: () => refresh(),
  });

  return (
    <div className="w-72 bg-white flex flex-col border-r border-gray-200 hidden md:flex z-30 flex-shrink-0">
      <div className="p-5 border-b border-gray-100 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-md shadow-blue-200">
          <i className="fa-solid fa-brain text-white text-sm"></i>
        </div>
        <div>
          <h1 className="font-bold text-lg tracking-tight text-blue-500">Smart Document Search System</h1>
          <p className="text-xs text-gray-500">v2.0</p>
        </div>
      </div>
      <div className="p-4">
        <button
          onClick={onNewChat}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 transition-all shadow-md active:scale-95"
        >
          <i className="fa-solid fa-plus text-sm"></i>
          <span className="font-medium text-sm">New Chat</span>
        </button>
      </div>
      <SessionList />
      <div className="px-3 py-3 border-t border-gray-100">
        <div className="flex items-center justify-between mb-2 px-1">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Documents</span>
          <button
            onClick={() => fileInputRef.current?.click()}
            title="Upload document"
            className="text-gray-400 hover:text-blue-600 transition-colors p-1 rounded"
          >
            <i className="fa-solid fa-upload text-xs"></i>
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept={SUPPORTED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) {
              if (!currentSessionId) {
                alert("Please start a new chat first.");
              } else {
                upload(file);
              }
            }
            e.target.value = "";
          }}
        />
        <UploadProgress visible={running} stage={stage} progress={progress} onCancel={abort} />
        <DocumentList />
      </div>
      <UserFooter />
    </div>
  );
}
