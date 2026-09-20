export interface DocumentItem {
  id: string;
  document_code: string;
  original_filename: string;
  stored_filename: string;
  file_extension: string;
  mime_type: string;
  file_size_bytes: number;
  ingestion_method: string;
  processing_status: string;
  sha256: string | null;
  normalized_text_sha256?: string | null;
  page_count?: number | null;
  text_length?: number | null;
  duplicate_status?: string | null;
  canonical_document_id?: string | null;
  duplicate_of_document_id?: string | null;
  possible_version_of_document_id?: string | null;
  similarity_score?: number | null;
  duplicate_checked_at?: string | null;
  duplicate_check_reason?: string | null;
  title: string | null;
  failure_reason: string | null;
  uploaded_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResult {
  items: DocumentItem[];
  page: number;
  page_size: number;
  total: number;
}

export interface DuplicateAnalysisResult {
  document_id: string;
  document_code: string;
  original_filename: string;
  classification: string;
  matched_document_id?: string | null;
  canonical_document_id?: string | null;
  similarity_score?: number | null;
  reasons: string[];
  diff_summary?: string | null;
  processing_status: string;
}
