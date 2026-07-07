export const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md"];

export function isSupportedFile(name: string): boolean {
  const lower = name.toLowerCase();
  return SUPPORTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

const ICONS_BY_EXTENSION: Record<string, string> = {
  ".pdf": "fa-file-pdf",
  ".docx": "fa-file-word",
  ".pptx": "fa-file-powerpoint",
  ".xlsx": "fa-file-excel",
  ".txt": "fa-file-lines",
  ".md": "fa-file-lines",
};

export function iconForFile(name: string): string {
  const lower = name.toLowerCase();
  const ext = SUPPORTED_EXTENSIONS.find((ext) => lower.endsWith(ext));
  return ext ? ICONS_BY_EXTENSION[ext] : "fa-file";
}
