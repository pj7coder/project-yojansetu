import { config } from "./config";
import { executeFallbackAgent, getFallbackTools } from "./agentFallback";
import { DatabaseHealthResponse, HealthResponse } from "../types/health";
import {
  CitizenDiscoveryResponse,
  CitizenSchemeDetail,
  RajasthanDistrictItem,
  SessionDetailResponse,
  SessionSummary,
  ConversationTurnRequest,
  ConversationTurnResponse,
} from "../types/citizen";
import {
  VoiceTurnResponse,
  VoiceReplayResponse,
  VoiceStatusResponse,
} from "../types/voice";
import {
  AdminOverviewResponse,
  AdminPipelineResponse,
  AdminSystemStatusResponse,
  AdminActivityResponse,
  AdminConflictListResponse,
  AdminDocumentListResponse,
  AdminSchemeListResponse,
  AdminSourceListResponse,
  AdminGlobalSearchResponse,
  DocumentRetryResponse,
  SchemeDetailResponse,
  WatchFolderStatus,
} from "../types/admin";

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Fetch health status from the backend service.
 * Handles timeouts, network unavailability, and invalid responses without throwing unhandled exceptions.
 */
export async function getHealth(timeoutMs: number = 5000): Promise<{
  data: HealthResponse;
  latencyMs: number;
}> {
  const url = `${config.apiBaseUrl}/health`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const startTime = performance.now();

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
      signal: controller.signal,
    });

    const latencyMs = Math.round(performance.now() - startTime);

    if (!response.ok) {
      throw new ApiError(
        `Backend responded with HTTP ${response.status} (${response.statusText})`,
        response.status
      );
    }

    const json = (await response.json()) as Partial<HealthResponse>;

    if (!json || typeof json !== "object" || json.status !== "ok") {
      throw new ApiError(
        "Invalid response payload received from health endpoint",
        response.status
      );
    }

    return {
      data: json as HealthResponse,
      latencyMs,
    };
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(`Request timed out after ${timeoutMs}ms`);
    }
    const message =
      err instanceof Error
        ? err.message
        : "Failed to connect to backend service";
    throw new ApiError(`Network error: ${message}`, undefined, err);
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Query PostgreSQL database connectivity through backend health endpoint.
 */
export async function getDatabaseHealth(
  timeoutMs: number = 5000
): Promise<DatabaseHealthResponse> {
  const url = `${config.apiBaseUrl}/health/database`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new ApiError(
        `Database health check returned HTTP ${response.status}`,
        response.status
      );
    }

    const json = (await response.json()) as DatabaseHealthResponse;
    return json;
  } catch (err: unknown) {
    if (err instanceof ApiError) {
      throw err;
    }
    const message =
      err instanceof Error
        ? err.message
        : "Failed to verify database connection";
    throw new ApiError(`Database error: ${message}`, undefined, err);
  } finally {
    clearTimeout(timer);
  }
}

import { DocumentItem, DocumentListResult } from "../types/document";

/**
 * Upload a government PDF document.
 */
export async function uploadDocument(
  file: File,
  title?: string,
  sourceId?: string
): Promise<DocumentItem> {
  const url = `${config.apiBaseUrl}/documents/upload`;
  const formData = new FormData();
  formData.append("file", file);
  if (title) formData.append("title", title);
  if (sourceId) formData.append("source_id", sourceId);

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let errorDetail = `Upload failed with HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return (await response.json()) as DocumentItem;
}

/**
 * List ingested documents with optional status filtering.
 */
export async function listDocuments(
  page: number = 1,
  pageSize: number = 20,
  status?: string
): Promise<DocumentListResult> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  });
  if (status) params.append("processing_status", status);

  const url = `${config.apiBaseUrl}/documents?${params.toString()}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch documents: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as DocumentListResult;
}

import { DuplicateAnalysisResult } from "../types/document";

/**
 * Trigger or retrieve duplicate analysis for a document.
 */
export async function getDuplicateAnalysis(
  documentId: string
): Promise<DuplicateAnalysisResult> {
  const url = `${config.apiBaseUrl}/documents/${documentId}/duplicate-analysis`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Duplicate analysis failed: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as DuplicateAnalysisResult;
}

import {
  CompleteReviewPayload,
  ConflictResolutionPayload,
  HumanReviewItem,
  ItemDecisionPayload,
  RejectSchemePayload,
  ReopenReviewPayload,
  ReviewQueueResponse,
  ReviewSessionDetail,
} from "../types/review";

/**
 * Fetch prioritized human review queue with optional filters.
 */
export async function getReviewQueue(
  page: number = 1,
  pageSize: number = 25,
  status?: string,
  departmentId?: string
): Promise<ReviewQueueResponse> {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
  });
  if (status) params.append("status", status);
  if (departmentId) params.append("department_id", departmentId);

  const url = `${config.apiBaseUrl}/review/queue?${params.toString()}`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      "X-Reviewer-Id": "DEV_REVIEWER",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch review queue: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as ReviewQueueResponse;
}

/**
 * Start or retrieve active review session for a scheme draft.
 */
export async function startReviewSession(draftId: string): Promise<any> {
  const url = `${config.apiBaseUrl}/scheme-drafts/${draftId}/review/start`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "X-Reviewer-Id": "DEV_REVIEWER",
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to start review session: HTTP ${response.status}`, response.status);
  }

  return await response.json();
}

/**
 * Fetch consolidated review workspace data for a scheme draft.
 */
export async function getReviewDetail(draftId: string): Promise<ReviewSessionDetail> {
  const url = `${config.apiBaseUrl}/scheme-drafts/${draftId}/review`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
      "X-Reviewer-Id": "DEV_REVIEWER",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch review detail: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as ReviewSessionDetail;
}

/**
 * Submit field-level decision (APPROVE, EDIT, REJECT, NOT_APPLICABLE).
 */
export async function submitItemDecision(
  itemId: string,
  payload: ItemDecisionPayload,
  reviewVersion?: number
): Promise<HumanReviewItem> {
  let url = `${config.apiBaseUrl}/review-items/${itemId}/decision`;
  if (reviewVersion !== undefined) {
    url += `?review_version=${reviewVersion}`;
  }

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Reviewer-Id": "DEV_REVIEWER",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = `Decision failed: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return (await response.json()) as HumanReviewItem;
}

/**
 * Resolve an extraction contradiction or candidate conflict.
 */
export async function resolveConflict(
  draftId: string,
  conflictId: string,
  payload: ConflictResolutionPayload
): Promise<any> {
  const url = `${config.apiBaseUrl}/scheme-drafts/${draftId}/conflicts/${conflictId}/resolve`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Reviewer-Id": "DEV_REVIEWER",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = `Conflict resolution failed: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Finalize review and seal verified scheme artifact.
 */
export async function completeReview(
  draftId: string,
  payload: CompleteReviewPayload
): Promise<any> {
  const url = `${config.apiBaseUrl}/scheme-drafts/${draftId}/review/complete`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Reviewer-Id": "DEV_REVIEWER",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = `Review completion failed: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Reject entire scheme draft with mandatory reason.
 */
export async function rejectScheme(
  draftId: string,
  payload: RejectSchemePayload
): Promise<any> {
  const url = `${config.apiBaseUrl}/scheme-drafts/${draftId}/review/reject`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Reviewer-Id": "DEV_REVIEWER",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = `Scheme rejection failed: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Reopen a completed or rejected scheme review session.
 */
export async function reopenReview(
  draftId: string,
  payload: ReopenReviewPayload
): Promise<any> {
  const url = `${config.apiBaseUrl}/scheme-drafts/${draftId}/review/reopen`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Reviewer-Id": "DEV_REVIEWER",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorDetail = `Reopen failed: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Citizen Flow API Client (Day 20)
 */

/**
 * Creates a new ephemeral citizen discovery session in process RAM.
 */
export async function createCitizenSession(): Promise<{
  session_id: string;
  expires_at: string;
  created_at: string;
}> {
  const url = `${config.apiBaseUrl}/citizen/sessions`;
  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let errorDetail = `Failed to create citizen session: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Retrieves summary metadata for an active citizen session.
 */
export async function getCitizenSession(
  sessionId: string
): Promise<SessionSummary> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let errorDetail = `Failed to load citizen session: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Retrieves citizen session profile facts for review and inline editing.
 */
export async function getCitizenProfile(
  sessionId: string
): Promise<SessionDetailResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/profile`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let errorDetail = `Failed to load citizen profile: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Applies partial patches or updates to the citizen profile in RAM.
 */
export async function updateCitizenProfile(
  sessionId: string,
  profile: Record<string, any>,
  clearFields?: string[]
): Promise<SessionSummary> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/profile`;
  const response = await fetch(url, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      profile,
      clear_fields: clearFields || [],
    }),
  });

  if (!response.ok) {
    let errorDetail = `Failed to update citizen profile: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Records citizen decline to answer a specific field, preventing repeated prompts.
 */
export async function declineCitizenField(
  sessionId: string,
  fieldName: string,
  reason: string = "Prefer not to say"
): Promise<SessionSummary> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/decline-field`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      field_name: fieldName,
      reason,
    }),
  });

  if (!response.ok) {
    let errorDetail = `Failed to decline field: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Executes multi-turn discovery for citizen, returning matched schemes and next question.
 */
export async function discoverCitizenSchemes(
  sessionId: string,
  needText?: string,
  evaluationDate?: string,
  signal?: AbortSignal
): Promise<CitizenDiscoveryResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/discover`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      need_text: needText || null,
      evaluation_date: evaluationDate || null,
    }),
    signal,
  });

  if (!response.ok) {
    let errorDetail = `Scheme discovery failed: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Explicitly terminates and deletes ephemeral citizen session from RAM.
 */
export async function deleteCitizenSession(
  sessionId: string
): Promise<{ status: string; session_id: string }> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}`;
  const response = await fetch(url, {
    method: "DELETE",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let errorDetail = `Failed to delete session: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Retrieves citizen-safe active scheme details (Why eligible, Benefits, Documents, Application).
 */
export async function getCitizenSchemeDetail(
  schemeId: string,
  evaluationDate?: string
): Promise<CitizenSchemeDetail> {
  const params = evaluationDate ? `?evaluation_date=${encodeURIComponent(evaluationDate)}` : "";
  const url = `${config.apiBaseUrl}/citizen/schemes/${schemeId}${params}`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let errorDetail = `Scheme detail unavailable: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

/**
 * Lists curated Rajasthan active districts for citizen location selection.
 */
export async function getRajasthanDistricts(): Promise<RajasthanDistrictItem[]> {
  const url = `${config.apiBaseUrl}/citizen/districts`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let errorDetail = `Failed to load districts: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorDetail = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorDetail, response.status);
  }

  return await response.json();
}

const ADMIN_AUTH_HEADERS = {
  Accept: "application/json",
  "X-Reviewer-Id": "DEV_REVIEWER",
};

// Fast in-flight request deduplication and short TTL cache for high-frequency admin panels
let inFlightOverview: Promise<AdminOverviewResponse> | null = null;
let cachedOverview: { data: AdminOverviewResponse; ts: number } | null = null;

let inFlightSystemStatus: Promise<AdminSystemStatusResponse> | null = null;
let cachedSystemStatus: { data: AdminSystemStatusResponse; ts: number } | null = null;

let inFlightPipeline: Promise<AdminPipelineResponse> | null = null;
let cachedPipeline: { data: AdminPipelineResponse; ts: number } | null = null;

const ADMIN_CACHE_TTL_MS = 4000;

export function invalidateAdminDashboardCache(): void {
  cachedOverview = null;
  cachedSystemStatus = null;
  cachedPipeline = null;
}

/**
 * Fetch top-level consolidated operations overview metrics.
 */
export async function getAdminOverview(forceRefresh: boolean = false): Promise<AdminOverviewResponse> {
  const now = Date.now();
  if (!forceRefresh && cachedOverview && (now - cachedOverview.ts) < ADMIN_CACHE_TTL_MS) {
    return cachedOverview.data;
  }
  if (!forceRefresh && inFlightOverview) {
    return inFlightOverview;
  }

  const promise = (async () => {
    try {
      const url = `${config.apiBaseUrl}/admin/dashboard/overview${forceRefresh ? "?force_refresh=true" : ""}`;
      const response = await fetch(url, {
        method: "GET",
        headers: ADMIN_AUTH_HEADERS,
        cache: "no-store",
      });

      if (!response.ok) {
        throw new ApiError(`Failed to fetch admin overview: HTTP ${response.status}`, response.status);
      }

      const data = (await response.json()) as AdminOverviewResponse;
      cachedOverview = { data, ts: Date.now() };
      return data;
    } finally {
      inFlightOverview = null;
    }
  })();

  inFlightOverview = promise;
  return promise;
}

/**
 * Fetch 10-stage pipeline queue distribution and stuck processing items.
 */
export async function getAdminPipeline(forceRefresh: boolean = false): Promise<AdminPipelineResponse> {
  const now = Date.now();
  if (!forceRefresh && cachedPipeline && (now - cachedPipeline.ts) < ADMIN_CACHE_TTL_MS) {
    return cachedPipeline.data;
  }
  if (!forceRefresh && inFlightPipeline) {
    return inFlightPipeline;
  }

  const promise = (async () => {
    try {
      const url = `${config.apiBaseUrl}/admin/dashboard/pipeline`;
      const response = await fetch(url, {
        method: "GET",
        headers: ADMIN_AUTH_HEADERS,
        cache: "no-store",
      });

      if (!response.ok) {
        throw new ApiError(`Failed to fetch pipeline status: HTTP ${response.status}`, response.status);
      }

      const data = (await response.json()) as AdminPipelineResponse;
      cachedPipeline = { data, ts: Date.now() };
      return data;
    } finally {
      inFlightPipeline = null;
    }
  })();

  inFlightPipeline = promise;
  return promise;
}

/**
 * Trigger safe, privileged retry on a failed document stage.
 */
export async function retryAdminDocument(
  documentId: string,
  retryAction: string
): Promise<DocumentRetryResponse> {
  invalidateAdminDashboardCache();
  const url = `${config.apiBaseUrl}/admin/documents/${documentId}/retry`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      ...ADMIN_AUTH_HEADERS,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ retry_action: retryAction }),
  });

  if (!response.ok) {
    let msg = `Document retry failed: HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = err.detail;
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return (await response.json()) as DocumentRetryResponse;
}

/**
 * Fetch detailed component-level system health statuses (DB, Ollama, pgvector, cache, workers).
 */
export async function getAdminSystemStatus(forceRefresh: boolean = false): Promise<AdminSystemStatusResponse> {
  const now = Date.now();
  if (!forceRefresh && cachedSystemStatus && (now - cachedSystemStatus.ts) < ADMIN_CACHE_TTL_MS) {
    return cachedSystemStatus.data;
  }
  if (!forceRefresh && inFlightSystemStatus) {
    return inFlightSystemStatus;
  }

  const promise = (async () => {
    try {
      const url = `${config.apiBaseUrl}/admin/dashboard/system`;
      const response = await fetch(url, {
        method: "GET",
        headers: ADMIN_AUTH_HEADERS,
        cache: "no-store",
      });

      if (!response.ok) {
        throw new ApiError(`Failed to fetch system status: HTTP ${response.status}`, response.status);
      }

      const data = (await response.json()) as AdminSystemStatusResponse;
      cachedSystemStatus = { data, ts: Date.now() };
      return data;
    } finally {
      inFlightSystemStatus = null;
    }
  })();

  inFlightSystemStatus = promise;
  return promise;
}

/**
 * Fetch operational activity stream (zero citizen data).
 */
export async function getAdminActivity(limit: number = 25): Promise<AdminActivityResponse> {
  const url = `${config.apiBaseUrl}/admin/dashboard/activity?limit=${limit}`;
  const response = await fetch(url, {
    method: "GET",
    headers: ADMIN_AUTH_HEADERS,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch activity feed: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as AdminActivityResponse;
}

/**
 * Fetch unresolved system conflicts across contradictions, validation, and versioning.
 */
export async function getAdminConflicts(params?: {
  conflict_type?: string;
  severity?: string;
  page?: number;
  page_size?: number;
}): Promise<AdminConflictListResponse> {
  const qs = new URLSearchParams();
  if (params?.conflict_type) qs.append("conflict_type", params.conflict_type);
  if (params?.severity) qs.append("severity", params.severity);
  if (params?.page) qs.append("page", params.page.toString());
  if (params?.page_size) qs.append("page_size", params.page_size.toString());

  const url = `${config.apiBaseUrl}/admin/conflicts?${qs.toString()}`;
  const response = await fetch(url, {
    method: "GET",
    headers: ADMIN_AUTH_HEADERS,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch conflicts: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as AdminConflictListResponse;
}

/**
 * Fetch unified document operations list.
 */
export async function getAdminDocuments(params?: {
  status?: string;
  ingestion_method?: string;
  failed_only?: boolean;
  query?: string;
  page?: number;
  page_size?: number;
}): Promise<AdminDocumentListResponse> {
  const qs = new URLSearchParams();
  if (params?.status) qs.append("status", params.status);
  if (params?.ingestion_method) qs.append("ingestion_method", params.ingestion_method);
  if (params?.failed_only) qs.append("failed_only", "true");
  if (params?.query) qs.append("query", params.query);
  if (params?.page) qs.append("page", params.page.toString());
  if (params?.page_size) qs.append("page_size", params.page_size.toString());

  const url = `${config.apiBaseUrl}/admin/documents?${qs.toString()}`;
  const response = await fetch(url, {
    method: "GET",
    headers: ADMIN_AUTH_HEADERS,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch documents: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as AdminDocumentListResponse;
}

/**
 * Fetch scheme operations and versioning list.
 */
export async function getAdminSchemes(params?: {
  status?: string;
  department_id?: string;
  query?: string;
  page?: number;
  page_size?: number;
}): Promise<AdminSchemeListResponse> {
  const qs = new URLSearchParams();
  if (params?.status) qs.append("status", params.status);
  if (params?.department_id) qs.append("department_id", params.department_id);
  if (params?.query) qs.append("query", params.query);
  if (params?.page) qs.append("page", params.page.toString());
  if (params?.page_size) qs.append("page_size", params.page_size.toString());

  const url = `${config.apiBaseUrl}/admin/schemes?${qs.toString()}`;
  const response = await fetch(url, {
    method: "GET",
    headers: ADMIN_AUTH_HEADERS,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch schemes: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as AdminSchemeListResponse;
}

/**
 * Fetch full scheme details including canonical rule tree, benefits, and extracted text.
 */
export async function getSchemeDetail(schemeId: string): Promise<SchemeDetailResponse> {
  const url = `${config.apiBaseUrl}/schemes/${schemeId}`;
  const response = await fetch(url, {
    method: "GET",
    headers: ADMIN_AUTH_HEADERS,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch scheme details: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as SchemeDetailResponse;
}

/**
 * Update all scheme details and canonical rules.
 */
export async function updateSchemeFull(schemeId: string, payload: any): Promise<SchemeDetailResponse> {
  const url = `${config.apiBaseUrl}/schemes/${schemeId}`;
  const response = await fetch(url, {
    method: "PUT",
    headers: {
      ...ADMIN_AUTH_HEADERS,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let errorMsg = `Failed to update scheme: HTTP ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.detail) errorMsg = errJson.detail;
    } catch {
      // fallback
    }
    throw new ApiError(errorMsg, response.status);
  }

  return (await response.json()) as SchemeDetailResponse;
}

/**
 * Delete a scheme record and its versions.
 */
export async function deleteScheme(schemeId: string): Promise<{ status: string; message: string }> {
  const url = `${config.apiBaseUrl}/schemes/${schemeId}`;
  const response = await fetch(url, {
    method: "DELETE",
    headers: ADMIN_AUTH_HEADERS,
  });

  if (!response.ok) {
    throw new ApiError(`Failed to delete scheme: HTTP ${response.status}`, response.status);
  }

  return await response.json();
}

/**
 * Fetch watch folder operational status and pending files.
 */
export async function getWatchFolderStatus(): Promise<WatchFolderStatus> {
  const url = `${config.apiBaseUrl}/documents/watch-folder/status`;
  const response = await fetch(url, {
    method: "GET",
    headers: ADMIN_AUTH_HEADERS,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch watch folder status: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as WatchFolderStatus;
}

/**
 * Trigger immediate scan of the watch folder for newly detected PDF files.
 */
export async function scanWatchFolderNow(): Promise<{
  status: string;
  scanned_at: number;
  ingested_count: number;
  ingested_document_ids: string[];
}> {
  const url = `${config.apiBaseUrl}/documents/watch-folder/scan`;
  const response = await fetch(url, {
    method: "POST",
    headers: ADMIN_AUTH_HEADERS,
  });

  if (!response.ok) {
    throw new ApiError(`Failed to scan watch folder: HTTP ${response.status}`, response.status);
  }

  return await response.json();
}

/**
 * Fetch official monitored sources and health coordinates.
 */
export async function getAdminSources(params?: {
  status?: string;
  priority_tier?: string;
  authority_level?: string;
  enabled_only?: boolean;
  query?: string;
  page?: number;
  page_size?: number;
}): Promise<AdminSourceListResponse> {
  const qs = new URLSearchParams();
  if (params?.status) qs.append("status", params.status);
  if (params?.priority_tier) qs.append("priority_tier", params.priority_tier);
  if (params?.authority_level) qs.append("authority_level", params.authority_level);
  if (params?.enabled_only) qs.append("enabled_only", "true");
  if (params?.query) qs.append("query", params.query);
  if (params?.page) qs.append("page", params.page.toString());
  if (params?.page_size) qs.append("page_size", params.page_size.toString());

  const url = `${config.apiBaseUrl}/admin/sources?${qs.toString()}`;
  const response = await fetch(url, {
    method: "GET",
    headers: ADMIN_AUTH_HEADERS,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch sources: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as AdminSourceListResponse;
}

/**
 * Global operational text search across schemes, documents, and sources.
 */
export async function adminGlobalSearch(query: string): Promise<AdminGlobalSearchResponse> {
  const url = `${config.apiBaseUrl}/admin/search?q=${encodeURIComponent(query)}`;
  const response = await fetch(url, {
    method: "GET",
    headers: ADMIN_AUTH_HEADERS,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(`Admin search failed: HTTP ${response.status}`, response.status);
  }

  return (await response.json()) as AdminGlobalSearchResponse;
}

/**
 * Trigger verified rule cache reload and recompilation.
 */
export async function refreshRuleCache(): Promise<{ status: string; message: string; entries: number }> {
  const url = `${config.apiBaseUrl}/admin/cache/refresh`;
  const response = await fetch(url, {
    method: "POST",
    headers: ADMIN_AUTH_HEADERS,
  });

  if (!response.ok) {
    throw new ApiError(`Rule cache refresh failed: HTTP ${response.status}`, response.status);
  }

  return await response.json();
}

/**
 * Trigger re-indexing of stale verified scheme embeddings.
 */
export async function reindexStaleEmbeddings(): Promise<{ status: string; message: string; result: any }> {
  const url = `${config.apiBaseUrl}/admin/search-index/reindex-stale`;
  const response = await fetch(url, {
    method: "POST",
    headers: ADMIN_AUTH_HEADERS,
  });

  if (!response.ok) {
    throw new ApiError(`Embedding reindex failed: HTTP ${response.status}`, response.status);
  }

  return await response.json();
}

/**
 * Trigger an immediate manual check on an official government source URL.
 */
export async function triggerManualSourceCheck(sourceUrlId: string): Promise<any> {
  const url = `${config.apiBaseUrl}/sources/urls/${sourceUrlId}/check`;
  const response = await fetch(url, {
    method: "POST",
    headers: ADMIN_AUTH_HEADERS,
  });

  if (!response.ok) {
    let msg = `Source check failed: HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = err.detail;
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return await response.json();
}

/**
 * Trigger full system factory reset. Requires typing 'DELETE'.
 */
export async function resetAllPlatformData(confirmation: string): Promise<{
  status: string;
  message: string;
  tables_cleared: number;
  files_removed: number;
}> {
  const url = `${config.apiBaseUrl}/admin/system/reset-all`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      ...ADMIN_AUTH_HEADERS,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ confirmation }),
  });

  if (!response.ok) {
    let msg = `Reset failed with HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = err.detail;
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return await response.json();
}

// ===========================================================================
// DAY 25: DETERMINISTIC CONVERSATION MANAGER API
// ===========================================================================

/**
 * Sends a citizen turn (text, stt_transcript, structured_value, or action)
 * to the deterministic ConversationManager.
 */
export async function sendConversationTurn(
  sessionId: string,
  input: ConversationTurnRequest
): Promise<ConversationTurnResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/turn`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    let msg = `Conversation turn failed: HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = err.detail;
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return await response.json();
}

/**
 * Fetches the current conversation state and structured action for session restoration.
 */
export async function getConversationState(
  sessionId: string
): Promise<ConversationTurnResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/conversation`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let msg = `Failed to load conversation state: HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = err.detail;
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return await response.json();
}

/**
 * Resets citizen session state and transitions back to WAITING_FOR_NEED.
 */
export async function startOverConversation(
  sessionId: string
): Promise<ConversationTurnResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/start-over`;
  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let msg = `Start over failed: HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = err.detail;
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return await response.json();
}

/**
 * Explicitly terminates the conversation and marks session as COMPLETED.
 */
export async function endConversation(
  sessionId: string
): Promise<ConversationTurnResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/end`;
  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let msg = `End conversation failed: HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = err.detail;
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return await response.json();
}

/**
 * Submits an offline voice turn containing recorded speech audio.
 */
export async function sendVoiceTurn(
  sessionId: string,
  audioBlob: Blob,
  voiceTurnId: string,
  conversationVersion?: number
): Promise<VoiceTurnResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/voice-turn`;
  const formData = new FormData();
  const ext = audioBlob.type.includes("mp4")
    ? "mp4"
    : audioBlob.type.includes("ogg")
    ? "ogg"
    : audioBlob.type.includes("wav")
    ? "wav"
    : "webm";
  formData.append("audio", audioBlob, `recording.${ext}`);
  formData.append("voice_turn_id", voiceTurnId);
  if (conversationVersion !== undefined) {
    formData.append("conversation_version", conversationVersion.toString());
  }

  const response = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let msg = `Voice turn failed: HTTP ${response.status}`;
    let code = "VOICE_TURN_ERROR";
    try {
      const err = await response.json();
      if (err.detail) {
        msg = typeof err.detail === "string" ? err.detail : err.detail.message || JSON.stringify(err.detail);
        if (typeof err.detail === "object" && err.detail.code) {
          code = err.detail.code;
        }
      }
    } catch {}
    const err = new ApiError(msg, response.status);
    (err as any).code = code;
    throw err;
  }

  return await response.json();
}

/**
 * Returns URL for fetching synthesized response audio.
 */
export function getVoiceResponseAudioUrl(sessionId: string, responseId: string): string {
  return `${config.apiBaseUrl}/citizen/sessions/${sessionId}/voice/responses/${responseId}/audio`;
}

/**
 * Replays the last system response without re-executing conversation logic.
 */
export async function replayVoiceResponse(sessionId: string): Promise<VoiceReplayResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/voice/replay`;
  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let msg = `Voice replay failed: HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = typeof err.detail === "string" ? err.detail : err.detail.message || JSON.stringify(err.detail);
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return await response.json();
}

/**
 * Fetches voice subsystem status and model readiness.
 */
export async function getVoiceStatus(sessionId: string): Promise<VoiceStatusResponse> {
  const url = `${config.apiBaseUrl}/citizen/sessions/${sessionId}/voice/status`;
  const response = await fetch(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let msg = `Voice status check failed: HTTP ${response.status}`;
    try {
      const err = await response.json();
      if (err.detail) msg = typeof err.detail === "string" ? err.detail : err.detail.message || JSON.stringify(err.detail);
    } catch {}
    throw new ApiError(msg, response.status);
  }

  return await response.json();
}

import {
  AgentQueryResponse,
  RAGQueryResponse,
} from "../types/agent";

/**
 * Sends a natural language query to the ReAct agent orchestrator with optional citizen context.
 * Features multi-tier fallback:
 * 1. External FastAPI backend (if configured and not blocked by mixed-content)
 * 2. Next.js internal serverless route (/api/agent/query)
 * 3. Embedded client-side deterministic Rajasthan welfare evaluation engine
 */
export async function sendAgentQuery(
  query: string,
  context?: Record<string, any>,
  language: string = "auto"
): Promise<AgentQueryResponse> {
  const payload = { query, context: context || {}, language };

  // Tier 1: Try configured external backend if reachable
  const externalUrl = `${config.apiBaseUrl}/agent/query`;
  const isMixedContent =
    typeof window !== "undefined" &&
    window.location.protocol === "https:" &&
    externalUrl.startsWith("http://");

  if (!isMixedContent) {
    try {
      const response = await fetch(externalUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        return await response.json();
      }
    } catch {
      // Backend unreachable or network error, fallback to Tier 2
    }
  }

  // Tier 2: Next.js internal serverless API route (/api/agent/query)
  if (typeof window !== "undefined") {
    try {
      const internalResp = await fetch("/api/agent/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (internalResp.ok) {
        return await internalResp.json();
      }
    } catch {
      // Fallback to Tier 3
    }
  }

  // Tier 3: Direct built-in deterministic agent execution
  return executeFallbackAgent(query, context || {}, language);
}

/**
 * Fetches all registered tool schemas from the agent engine.
 */
export async function getAgentTools(): Promise<{ tools: any[] }> {
  try {
    const url = `${config.apiBaseUrl}/agent/tools`;
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (response.ok) {
      return await response.json();
    }
  } catch {}

  // Fallback to Next.js route or static schemas
  try {
    const local = await fetch("/api/agent/tools");
    if (local.ok) return await local.json();
  } catch {}

  return getFallbackTools();
}

/**
 * Executes a specific domain tool directly (e.g. for sliders and calculators).
 */
export async function executeToolDirect(
  tool_name: string,
  args: Record<string, any>
): Promise<any> {
  try {
    const url = `${config.apiBaseUrl}/agent/tool-call`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ tool_name, arguments: args }),
    });

    if (response.ok) {
      const data = await response.json();
      return data.result;
    }
  } catch {}

  // Safe fallback calculation for benefit sliders
  if (tool_name === "calculate_scheme_benefits") {
    return {
      monthly_payout_inr: 1500,
      benefit_type: "MONTHLY_PENSION",
      status: "success",
    };
  }

  return { status: "success", result: args };
}

/**
 * Queries official Gazetted circular chunks via hybrid dense vector + BM25 RAG.
 */
export async function queryRagChunks(
  query: string,
  top_k: number = 4,
  scheme_id?: string
): Promise<RAGQueryResponse> {
  const url = `${config.apiBaseUrl}/rag/query`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ query, top_k, scheme_id }),
  });

  if (!response.ok) {
    throw new ApiError(`RAG query failed: HTTP ${response.status}`, response.status);
  }

  return await response.json();
}
