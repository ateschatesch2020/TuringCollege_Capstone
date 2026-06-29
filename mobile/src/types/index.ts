export interface Session {
  session_id: string;
  title: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface UploadEvent {
  stage: string;
  progress?: number;
  error?: string;
}
