export interface Session {
  session_id: string;
  title: string;
  model: string;
  embedding_model: string;
}

export interface ModelOption {
  id: string;
  label: string;
  provider_name: string;
  type: "frontier" | "open_source";
  size_gb: number | null;
  context_length: number | null;
}

export interface EmbeddingModelOption {
  id: string;
  label: string;
  provider_name: string;
  dimensions: number;
  location: "api" | "local";
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface FileSelectEntry {
  name: string;
  path: string;
  size_bytes: number;
}

export interface TokenUsage {
  percent: number | null;
  [key: string]: unknown;
}

export interface EvaluationMetrics {
  answer_relevancy?: number;
  faithfulness?: number;
  context_precision?: number;
  context_recall?: number;
}

export interface EvaluationSideResult extends EvaluationMetrics {
  rag_answer: string;
}

export interface EvaluationRow {
  question: string;
  expected_answer: string;
  results: Record<string, EvaluationSideResult>;
}

export interface StrategyRow extends EvaluationSideResult {
  question: string;
  expected_answer: string;
}

export interface SSEEvent {
  stage?: string;
  progress?: number;
  error?: string;
  result?: string;
  results?: unknown[];
  chunks?: number;
  filename?: string;
  file_index?: number;
  total_files?: number;
  [key: string]: unknown;
}
