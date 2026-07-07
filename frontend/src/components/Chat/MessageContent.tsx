import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import FileSelectWidget from "./FileSelectWidget.tsx";
import type { FileSelectEntry } from "../../types";

interface MessageContentProps {
  text: string;
  sessionId: string;
  embeddingModelId?: string;
}

export default function MessageContent({ text, sessionId, embeddingModelId }: MessageContentProps) {
  return (
    <div className="message-content text-[15px] leading-relaxed break-text">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            if (className === "language-file-select") {
              let files: FileSelectEntry[] = [];
              try {
                files = JSON.parse(String(children));
              } catch {
                return null;
              }
              if (!Array.isArray(files) || files.length === 0) return null;
              return <FileSelectWidget files={files} sessionId={sessionId} embeddingModelId={embeddingModelId} />;
            }
            return (
              <code className={className} {...props}>
                {children}
              </code>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
