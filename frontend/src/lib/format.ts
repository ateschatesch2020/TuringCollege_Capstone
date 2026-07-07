export function formatFileSize(bytes: number | undefined | null): string {
  if (!bytes) return "?";
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

export function estimateUploadTime(bytes: number | undefined | null): string {
  const estSec = Math.max(15, Math.round((bytes || 0) / 20000));
  return estSec < 60 ? `~${estSec}s` : `~${Math.round(estSec / 60)}m`;
}

export function formatRemaining(sec: number): string {
  return sec < 60 ? `~${sec}s left` : `~${Math.round(sec / 60)} min left`;
}
