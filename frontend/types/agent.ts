export interface ToolExecutionStep {
  step: number;
  thought: string;
  tool_name: string;
  tool_args: Record<string, any>;
  tool_result: Record<string, any>;
  duration_ms: number;
}

export interface SchemeCitation {
  citation_tag: string;
  title: string;
  page: number;
  snippet: string;
}

export interface RecommendedScheme {
  scheme_code: string;
  name_en: string;
  name_hi: string;
  eligibility_status: string;
  benefit_summary?: string | any;
  benefit_details?: Record<string, any>;
  passed_conditions?: string[];
  documents_required?: string[];
}

export interface RequiredDocument {
  document_name: string;
  purpose: string;
  issued_by: string;
  is_mandatory: boolean;
}

export interface EmitraKioskInfo {
  district: string;
  tehsil: string;
  toll_free_helpline: string;
  emitra_support: string;
  working_hours: string;
  service_kiosks: Array<{
    kiosk_name: string;
    location: string;
    services: string[];
    govt_fee: string;
  }>;
  citizen_tip: string;
}

export interface AgentStructuredData {
  citations?: SchemeCitation[];
  recommended_schemes?: RecommendedScheme[];
  required_documents?: RequiredDocument[];
  emitra_kiosk_info?: EmitraKioskInfo;
  profile_extracted?: Record<string, any>;
}

export interface AgentQueryResponse {
  final_answer: string;
  language: string;
  steps: ToolExecutionStep[];
  structured_data: AgentStructuredData;
  execution_time_ms: number;
}

export interface RAGChunk {
  chunk_id: string;
  circular_id: string;
  title: string;
  page_number: number;
  text: string;
  score: number;
  citation_tag: string;
  metadata: Record<string, any>;
}

export interface RAGQueryResponse {
  query: string;
  chunks: RAGChunk[];
  total_retrieved: number;
}
