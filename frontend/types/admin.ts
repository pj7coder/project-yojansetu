export type SystemStatusType = 'HEALTHY' | 'WARNING' | 'CRITICAL';
export type IssueSeverity = 'CRITICAL' | 'WARNING' | 'ERROR' | 'INFO' | 'SUCCESS';

export interface SourceOverview {
  total: number;
  active: number;
  failing: number;
  recently_changed: number;
}

export interface DocumentOverview {
  total: number;
  processing: number;
  failed: number;
  waiting_review: number;
}

export interface PipelineStageCount {
  stage: string;
  waiting: number;
  processing: number;
  failed: number;
  oldest_waiting_seconds?: number | null;
}

export interface ReviewOverview {
  pending: number;
  critical: number;
  in_review: number;
}

export interface SchemeOverview {
  total: number;
  human_verified: number;
  active_versions: number;
  future_versions: number;
  superseded_versions: number;
}

export interface ConflictOverview {
  total_unresolved: number;
  critical_count: number;
}

export interface CriticalIssue {
  id: string;
  category: 'SOURCE' | 'DOCUMENT' | 'REVIEW' | 'CONFLICT' | 'VERSION' | string;
  severity: 'CRITICAL' | 'WARNING' | string;
  title: string;
  description: string;
  link: string;
  created_at: string;
}

export interface AdminOverviewResponse {
  system_status: SystemStatusType;
  system_status_reasons: string[];
  sources: SourceOverview;
  documents: DocumentOverview;
  reviews: ReviewOverview;
  schemes: SchemeOverview;
  conflicts: ConflictOverview;
  pipeline_stages: PipelineStageCount[];
  critical_issues: CriticalIssue[];
  generated_at: string;
}

export interface StuckItem {
  document_id: string;
  document_code: string;
  stage: string;
  status: string;
  elapsed_minutes: number;
  title?: string | null;
  retry_valid: boolean;
  valid_retry_action?: string | null;
}

export interface AdminPipelineResponse {
  stages: PipelineStageCount[];
  stuck_items: StuckItem[];
  total_waiting: number;
  total_processing: number;
  total_failed: number;
  generated_at: string;
}

export interface DatabaseHealth {
  status: 'HEALTHY' | 'UNAVAILABLE' | string;
  pool_size: number;
  overflow: number;
  latency_ms?: number | null;
}

export interface OllamaHealth {
  status: 'HEALTHY' | 'UNAVAILABLE' | string;
  model: string;
  model_available: boolean;
  provider: string;
}

export interface SearchIndexHealth {
  status: 'HEALTHY' | 'DEGRADED' | 'UNAVAILABLE' | string;
  verified_schemes_count: number;
  search_metadata_count: number;
  embeddings_count: number;
  stale_embeddings_count: number;
  embedding_model: string;
  pgvector_available: boolean;
}

export interface RuleCacheHealth {
  status: 'HEALTHY' | 'EMPTY' | 'WARNING' | string;
  entries: number;
  hits: number;
  misses: number;
  compile_failures: number;
  refreshes: number;
}

export interface WorkerHeartbeatItem {
  worker_type: string;
  worker_instance_id: string;
  last_seen_at: string;
  status: 'HEALTHY' | 'BUSY' | 'IDLE' | 'STOPPED' | string;
  is_stale: boolean;
  metadata_safe: Record<string, any>;
}

export interface StorageCountItem {
  original_documents: number;
  parsed_documents: number;
  ocr_runs: number;
  document_chunks: number;
  scheme_drafts: number;
  source_snapshots: number;
  verified_scheme_artifacts: number;
}

export interface AdminSystemStatusResponse {
  overall_status: SystemStatusType;
  database: DatabaseHealth;
  ollama: OllamaHealth;
  search_index: SearchIndexHealth;
  rule_cache: RuleCacheHealth;
  workers: WorkerHeartbeatItem[];
  storage: StorageCountItem;
  generated_at: string;
}

export interface AdminActivityItem {
  id: string;
  event_type: string;
  actor: string;
  title: string;
  description: string;
  target_id?: string | null;
  target_link?: string | null;
  timestamp: string;
  severity: IssueSeverity;
}

export interface AdminActivityResponse {
  items: AdminActivityItem[];
  total: number;
}

export interface AdminConflictItem {
  id: string;
  conflict_type: string;
  severity: 'CRITICAL' | 'WARNING' | string;
  title: string;
  description: string;
  scheme_id?: string | null;
  scheme_name?: string | null;
  document_id?: string | null;
  source_count: number;
  status: string;
  link: string;
  created_at: string;
}

export interface AdminConflictListResponse {
  items: AdminConflictItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminDocumentListItem {
  id: string;
  document_code: string;
  original_filename: string;
  source_name?: string | null;
  ingestion_method: string;
  processing_status: string;
  current_stage: string;
  page_count?: number | null;
  file_size_bytes: number;
  failure_reason?: string | null;
  retry_valid: boolean;
  valid_retry_action?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminDocumentListResponse {
  items: AdminDocumentListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DocumentRetryResponse {
  document_id: string;
  action_taken: string;
  new_status: string;
  message: string;
}

export interface AdminSchemeListItem {
  id: string;
  scheme_code: string;
  name_en: string;
  name_hi?: string | null;
  department_name?: string | null;
  scheme_origin: string;
  current_version_number?: number | null;
  current_version_status?: string | null;
  has_future_version: boolean;
  future_effective_date?: string | null;
  is_active: boolean;
  last_reviewed_at?: string | null;
}

export interface AdminSchemeListResponse {
  items: AdminSchemeListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminSourceListItem {
  id: string;
  source_url_id?: string | null;
  source_name: string;
  url: string;
  authority_level: string;
  priority_tier: string;
  monitor_status: string;
  last_check_at?: string | null;
  last_change_at?: string | null;
  next_check_at?: string | null;
  failure_count: number;
  enabled: boolean;
}

export interface AdminSourceListResponse {
  items: AdminSourceListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminSearchHit {
  id: string;
  entity_type: 'SCHEME' | 'DOCUMENT' | 'SOURCE' | string;
  title: string;
  subtitle?: string | null;
  code?: string | null;
  status?: string | null;
  link: string;
}

export interface AdminGlobalSearchResponse {
  query: string;
  schemes: AdminSearchHit[];
  documents: AdminSearchHit[];
  sources: AdminSearchHit[];
  total_hits: number;
}

export interface CanonicalBenefit {
  benefit_id?: string;
  type: string;
  amount?: number | null;
  currency?: string;
  frequency?: string;
  quantity?: number | null;
  unit?: string | null;
  description?: string;
  raw_amount_text?: string;
  raw_text?: string;
}

export interface EligibilityCondition {
  condition_id?: string;
  field: string;
  operator: string;
  value: any;
  value_type?: string;
  unit?: string | null;
  periodicity?: string | null;
  raw_text?: string;
}

export interface CanonicalExclusion {
  exclusion_id?: string;
  field?: string;
  raw_text?: string;
}

export interface CanonicalDocument {
  document_id?: string;
  document_type: string;
  name_raw: string;
  mandatory?: boolean | null;
  notes?: string | null;
}

export interface CanonicalApplication {
  channels?: string[];
  portal_url?: string | null;
  office?: string | null;
  steps?: string[];
  fees?: string | null;
  application_window?: string | null;
  notes?: string | null;
}

export interface CanonicalImportantDate {
  event_name: string;
  normalized_date?: string | null;
  raw_date_text?: string;
}

export interface CanonicalEvidenceItem {
  evidence_id: string;
  text: string;
  raw_value?: string;
  page_numbers?: number[];
  extraction_method?: string;
}

export interface SchemeDetailResponse {
  id: string;
  scheme_code: string;
  name_en: string;
  name_hi?: string | null;
  short_name?: string | null;
  department_id: string;
  department_name?: string | null;
  category_id: string;
  category_name?: string | null;
  short_description?: string | null;
  status: string;
  jurisdiction: string;
  scheme_origin: string;
  created_at: string;
  updated_at: string;
  active_version_number?: number;
  source_filename?: string | null;
  source_document_id?: string | null;
  canonical_data?: {
    scheme_identity?: {
      name?: { raw?: string; en?: string; hi?: string; short_name?: string };
      scheme_code?: string;
      department?: string | null;
      category?: string | null;
      description?: string | null;
    };
    scheme_code?: string;
    scope?: {
      state?: string;
      districts?: string[];
      rural_urban?: string;
      beneficiary_group?: string[];
    };
    benefits?: CanonicalBenefit[];
    eligibility?: {
      simple_fields?: Record<string, any>;
      conditions?: EligibilityCondition[];
      exclusions?: CanonicalExclusion[];
      root_rule?: any;
    };
    required_documents?: CanonicalDocument[];
    application?: CanonicalApplication;
    important_dates?: CanonicalImportantDate[];
    evidence_registry?: CanonicalEvidenceItem[];
    [key: string]: any;
  } | null;
  versions?: Array<{
    id: string;
    version_number: number;
    status: string;
    is_current: boolean;
    created_at: string;
  }>;
}

export interface WatchFolderStatus {
  enabled: boolean;
  folder_path: string;
  pending_count: number;
  pending_files: string[];
  is_running: boolean;
}

