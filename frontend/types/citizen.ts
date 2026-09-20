export type CitizenLanguage = "hi" | "en";

export interface QuestionOption {
  value: string;
  label_en: string;
  label_hi: string;
}

export interface CitizenQuestionDisplay {
  field: string;
  reason_code: string;
  data_type: "integer" | "currency" | "select" | "boolean" | "string" | "number";
  display_name_en: string;
  display_name_hi: string;
  question_en: string;
  question_hi: string;
  options?: QuestionOption[] | null;
  unit_en?: string | null;
  unit_hi?: string | null;
  sensitivity_level: "LOW" | "MEDIUM" | "HIGH";
  allow_decline: boolean;
  help_text_en?: string | null;
  help_text_hi?: string | null;
}

export interface CitizenSchemeCard {
  scheme_id: string;
  scheme_code: string;
  name_en: string;
  name_hi?: string | null;
  department_en?: string | null;
  department_hi?: string | null;
  purpose_en?: string | null;
  purpose_hi?: string | null;
  primary_benefit_en?: string | null;
  primary_benefit_hi?: string | null;
  eligibility_status: "ELIGIBLE" | "MORE_INFORMATION_REQUIRED" | string;
  why_eligible_summary_hi: string[];
  why_eligible_summary_en: string[];
  missing_fields: string[];
  missing_fields_display_hi: string[];
  missing_fields_display_en: string[];
}

export interface CitizenBenefitItem {
  benefit_type: string;
  amount?: number | null;
  currency: string;
  frequency?: string | null;
  description_en?: string | null;
  description_hi?: string | null;
  display_text_en?: string | null;
  display_text_hi?: string | null;
}

export interface CitizenDocumentItem {
  document_name_en: string;
  document_name_hi?: string | null;
  is_mandatory: boolean;
  description_en?: string | null;
  description_hi?: string | null;
}

export interface CitizenApplicationGuidance {
  channels: string[];
  portal_url?: string | null;
  is_portal_url_safe: boolean;
  submission_mode?: string | null;
  steps_en: string[];
  steps_hi: string[];
  fee_inr?: number | null;
  guidance_note_en: string;
  guidance_note_hi: string;
}

export interface CitizenSourceInfo {
  department_en?: string | null;
  department_hi?: string | null;
  notification_reference?: string | null;
  source_date?: string | null;
  page_reference?: string | null;
  official_url?: string | null;
}

export interface CitizenSchemeDetail {
  scheme_id: string;
  scheme_code: string;
  name_en: string;
  name_hi?: string | null;
  version_number: number;
  version_label?: string | null;
  status: string;
  is_active: boolean;
  effective_date?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  department_en?: string | null;
  department_hi?: string | null;
  category_en?: string | null;
  category_hi?: string | null;
  purpose_en?: string | null;
  purpose_hi?: string | null;
  why_eligible_hi: string[];
  why_eligible_en: string[];
  eligibility_conditions_hi: string[];
  eligibility_conditions_en: string[];
  benefits: CitizenBenefitItem[];
  required_documents: CitizenDocumentItem[];
  application: CitizenApplicationGuidance;
  important_dates: Array<Record<string, any>>;
  official_source: CitizenSourceInfo;
}

export interface SessionSummary {
  session_id: string;
  known_fields: string[];
  declined_fields: string[];
  asked_fields: string[];
  need_text?: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
  profile_version: number;
}

export interface CitizenDiscoveryResponse {
  session_id: string;
  state: "START" | "COLLECTING_INFORMATION" | "RESULTS_READY" | "NO_CANDIDATES" | "CANNOT_RESOLVE";
  message_hi: string;
  message_en: string;
  eligible: CitizenSchemeCard[];
  more_information_required: CitizenSchemeCard[];
  next_question?: CitizenQuestionDisplay | null;
  session_summary: SessionSummary;
  total_eligible_count: number;
  total_more_info_count: number;
}

export interface RajasthanDistrictItem {
  code: string;
  name_en: string;
  name_hi: string;
  aliases: string[];
  status: string;
}

export interface SessionDetailResponse {
  session_id: string;
  profile: Record<string, any>;
  known_fields: string[];
  declined_fields: string[];
  asked_fields: string[];
  need_text?: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
  profile_version: number;
}

// Day 25 Conversation Manager Types
export type ConversationState =
  | 'NEW_SESSION'
  | 'WAITING_FOR_NEED'
  | 'WAITING_FOR_PROFILE_VALUE'
  | 'WAITING_FOR_CONFIRMATION'
  | 'PROCESSING_DISCOVERY'
  | 'SHOWING_RESULTS'
  | 'WAITING_FOR_RESULT_ACTION'
  | 'HANDLING_CITIZEN_QUERY'
  | 'NEED_CLARIFICATION'
  | 'NO_RESULTS'
  | 'CANNOT_RESOLVE'
  | 'COMPLETED'
  | 'ERROR';

export type ConversationAction =
  | 'ASK_NEED'
  | 'ASK_PROFILE_FIELD'
  | 'CONFIRM_PROFILE_VALUE'
  | 'CLARIFY_PROFILE_VALUE'
  | 'SHOW_RESULTS'
  | 'SHOW_NO_RESULTS'
  | 'SHOW_CANNOT_RESOLVE'
  | 'ANSWER_FIELD_HELP'
  | 'ANSWER_SCHEME_QUERY'
  | 'REPEAT_PROMPT'
  | 'END_CONVERSATION'
  | 'ERROR';

export interface ConversationMessage {
  key: string;
  text_hi: string;
  text_en: string;
  field?: string | null;
  display_value?: string | null;
}

export interface ExpectedInputOption {
  value: any;
  label_hi: string;
  label_en: string;
}

export interface ExpectedInputDescriptor {
  type: string;
  field?: string | null;
  options?: ExpectedInputOption[] | null;
  placeholder_hi?: string | null;
  placeholder_en?: string | null;
  unit_hi?: string | null;
  unit_en?: string | null;
  allow_decline?: boolean;
}

export interface ConversationMeta {
  turn: number;
  state: string;
  version: number;
  expected_field?: string | null;
  processing_ms: number;
}

export interface ConversationTurnRequest {
  type: 'TEXT' | 'STT_TRANSCRIPT' | 'STRUCTURED_VALUE' | 'ACTION';
  text?: string | null;
  action?: string | null;
  field?: string | null;
  value?: any;
  client_turn_id?: string | null;
  language?: string | null;
  scheme_id?: string | null;
  conversation_version?: number | null;
}

export interface ConversationTurnResponse {
  session_id: string;
  state: ConversationState;
  action: ConversationAction;
  message: ConversationMessage;
  expected_input: ExpectedInputDescriptor;
  results?: {
    eligible: CitizenSchemeCard[];
    more_information_required: CitizenSchemeCard[];
    total_eligible_count: number;
    total_more_info_count: number;
  } | null;
  focused_scheme?: CitizenSchemeDetail | null;
  meta: ConversationMeta;
}

