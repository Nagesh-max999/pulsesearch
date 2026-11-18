export type DocumentStatus =
  | "UPLOADED"
  | "PROCESSING"
  | "TEXT_EXTRACTED"
  | "INDEXING"
  | "GENERATING_EMBEDDING"
  | "COMPLETED"
  | "FAILED";

export type SearchMode = "KEYWORD" | "SEMANTIC" | "HYBRID";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
}

export interface DocumentItem {
  id: string;
  title: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetail extends DocumentItem {
  chunk_count: number;
  chunk_previews: { chunk_index: number; content: string }[];
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DocumentUploadResponse {
  document: DocumentItem;
  job_id: string;
  message: string;
}

export interface SearchResultItem {
  document_id: string;
  title: string;
  snippet: string;
  score: number;
  matched_terms: string[];
  keyword_score: number | null;
  semantic_score: number | null;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  results: SearchResultItem[];
  total: number;
  page: number;
  page_size: number;
  latency_ms: number;
}

export interface AnalyticsSummary {
  total_searches: number;
  keyword_searches: number;
  semantic_searches: number;
  hybrid_searches: number;
  zero_result_searches: number;
  avg_latency_ms: number;
  top_queries: { query: string; count: number }[];
}

export interface DocumentAnalytics {
  total: number;
  by_status: Record<string, number>;
}

export interface AskCitation {
  document_id: string;
  title: string;
  snippet: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  citations: AskCitation[];
  latency_ms: number;
}
