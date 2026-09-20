export type ReviewDecision =
  | "PENDING"
  | "APPROVED"
  | "EDITED"
  | "REJECTED"
  | "NOT_APPLICABLE";

export type ReviewSessionStatus =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "BLOCKED"
  | "COMPLETED"
  | "REJECTED"
  | "STALE";

export type ConflictResolutionChoice =
  | "SELECT_VALUE"
  | "KEEP_CONDITIONAL"
  | "REJECT_FIELD"
  | "UNRESOLVED";

export interface ReviewQueueItem {
  draft_id: string;
  internal_scheme_code: string;
  scheme_name: string;
  department_name?: string | null;
  source_filename: string;
  document_id: string;
  draft_status: string;
  review_status: ReviewSessionStatus;
  critical_issues: number;
  contradicted_facts: number;
  insufficient_facts: number;
  ocr_risks: number;
  conflicts: number;
  total_facts: number;
  resolved_facts: number;
  last_updated: string;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ValidationIssueSummary {
  rule_code: string;
  severity: "BLOCKER" | "ERROR" | "WARNING" | "INFO";
  message: string;
  field_path: string;
}

export interface HumanReviewItem {
  id: string;
  review_session_id: string;
  scheme_draft_id: string;
  fact_id: string;
  field_path: string;
  item_type: string;
  risk_level: "BLOCKER" | "HIGH" | "MEDIUM" | "LOW" | "CLEAN";
  statement: string;
  original_value_json?: any;
  current_value_json?: any;
  raw_text?: string | null;
  evidence_refs: string[];
  evidence_text?: string | null;
  page_number?: number | null;
  block_id?: string | null;
  decision: ReviewDecision;
  reviewer_comment?: string | null;
  edit_reason?: string | null;
  override_reason?: string | null;
  validation_issues_summary?: ValidationIssueSummary[] | null;
  verification_result?: "SUPPORTED" | "CONTRADICTED" | "NOT_ENOUGH_EVIDENCE" | null;
  verification_reason_code?: string | null;
  ocr_risk: boolean;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
}

export interface ReviewAuditEvent {
  id: string;
  review_session_id: string;
  scheme_draft_id: string;
  reviewer_id: string;
  action_type: string;
  field_path?: string | null;
  item_id?: string | null;
  before_value_json?: any;
  after_value_json?: any;
  reason?: string | null;
  created_at: string;
}

export interface ConflictItem {
  conflict_id: string;
  field: string;
  status: string;
  explanation?: string | null;
  values: Array<{
    value: any;
    source_block_id?: string;
    page_number?: number;
    text_snippet?: string;
    source_type?: string;
  }>;
}

export interface ReviewSessionDetail {
  session_id: string;
  scheme_draft_id: string;
  document_id: string;
  internal_scheme_code: string;
  scheme_name: string;
  department_name?: string | null;
  reviewer_id: string;
  session_status: ReviewSessionStatus;
  draft_status: string;
  review_version: number;
  canonical_artifact_sha256: string;
  is_stale: boolean;
  notes?: string | null;
  summary: {
    total_items?: number;
    approved?: number;
    edited?: number;
    rejected?: number;
    not_applicable?: number;
    pending?: number;
  };
  items: HumanReviewItem[];
  conflicts: ConflictItem[];
  validation_summary?: any;
  verification_summary?: any;
  audit_events: ReviewAuditEvent[];
  started_at: string;
  completed_at?: string | null;
}

export interface ItemDecisionPayload {
  decision: ReviewDecision;
  edit_value?: any;
  reviewer_comment?: string;
  edit_reason?: string;
  override_reason?: string;
}

export interface ConflictResolutionPayload {
  choice: ConflictResolutionChoice;
  selected_value?: any;
  reason: string;
}

export interface CompleteReviewPayload {
  notes?: string;
  review_version: number;
}

export interface RejectSchemePayload {
  reason: string;
}

export interface ReopenReviewPayload {
  reason: string;
}
