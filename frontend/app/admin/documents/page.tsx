"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { getAdminDocuments, retryAdminDocument, uploadDocument, getWatchFolderStatus, scanWatchFolderNow, ApiError } from "../../../lib/api";
import { AdminDocumentListItem, WatchFolderStatus } from "../../../types/admin";
import { StatusBadge } from "../../../components/admin/StatusBadge";
import { DataTable } from "../../../components/admin/DataTable";

// ─── Pipeline stage definitions ──────────────────────────────────────────────

interface PipelineStage {
  key: string;
  label: string;
  icon: string;
  activeStatuses: string[];   // statuses that mean "running this stage right now"
  doneStatuses: string[];     // statuses that mean "this stage is done"
  failedStatuses: string[];   // statuses that mean "failed at this stage"
}

const PIPELINE_STAGES: PipelineStage[] = [
  {
    key: "ingest",
    label: "Ingest",
    icon: "📥",
    activeStatuses: [],
    doneStatuses: ["READY_FOR_DUPLICATE_CHECK", "DUPLICATE_CHECKING", "READY_FOR_PARSING",
      "PARSING", "PARSING_FAILED", "READY_FOR_OCR_CHECK", "OCR_CHECKING", "OCR_FAILED",
      "READY_FOR_CHUNKING", "CHUNKING", "CHUNKING_FAILED", "READY_FOR_EXTRACTION",
      "EXTRACTING", "EXTRACTION_FAILED", "READY_FOR_NORMALIZATION", "NORMALIZING",
      "NORMALIZATION_FAILED", "READY_FOR_VALIDATION", "VALIDATING", "VALIDATION_FAILED",
      "READY_FOR_HUMAN_REVIEW", "HUMAN_VERIFIED", "DUPLICATE", "VERSION_REVIEW_REQUIRED",
      "REQUIRES_MANUAL_REVIEW"],
    failedStatuses: ["INVALID"],
  },
  {
    key: "dedup",
    label: "Dedup",
    icon: "🔍",
    activeStatuses: ["READY_FOR_DUPLICATE_CHECK", "DUPLICATE_CHECKING"],
    doneStatuses: ["READY_FOR_PARSING", "PARSING", "PARSING_FAILED", "READY_FOR_OCR_CHECK",
      "OCR_CHECKING", "OCR_FAILED", "READY_FOR_CHUNKING", "CHUNKING", "CHUNKING_FAILED",
      "READY_FOR_EXTRACTION", "EXTRACTING", "EXTRACTION_FAILED", "READY_FOR_NORMALIZATION",
      "NORMALIZING", "NORMALIZATION_FAILED", "READY_FOR_VALIDATION", "VALIDATING",
      "VALIDATION_FAILED", "READY_FOR_HUMAN_REVIEW", "HUMAN_VERIFIED",
      "DUPLICATE", "VERSION_REVIEW_REQUIRED", "DUPLICATE_CHECK_FAILED", "REQUIRES_MANUAL_REVIEW"],
    failedStatuses: ["DUPLICATE_CHECK_FAILED"],
  },
  {
    key: "parse",
    label: "Parse",
    icon: "📄",
    activeStatuses: ["READY_FOR_PARSING", "PARSING"],
    doneStatuses: ["READY_FOR_OCR_CHECK", "OCR_CHECKING", "OCR_FAILED", "READY_FOR_CHUNKING",
      "CHUNKING", "CHUNKING_FAILED", "READY_FOR_EXTRACTION", "EXTRACTING",
      "EXTRACTION_FAILED", "READY_FOR_NORMALIZATION", "NORMALIZING", "NORMALIZATION_FAILED",
      "READY_FOR_VALIDATION", "VALIDATING", "VALIDATION_FAILED",
      "READY_FOR_HUMAN_REVIEW", "HUMAN_VERIFIED", "REQUIRES_MANUAL_REVIEW"],
    failedStatuses: ["PARSING_FAILED"],
  },
  {
    key: "ocr",
    label: "OCR",
    icon: "👁️",
    activeStatuses: ["READY_FOR_OCR_CHECK", "OCR_CHECKING"],
    doneStatuses: ["READY_FOR_CHUNKING", "CHUNKING", "CHUNKING_FAILED", "READY_FOR_EXTRACTION",
      "EXTRACTING", "EXTRACTION_FAILED", "READY_FOR_NORMALIZATION", "NORMALIZING",
      "NORMALIZATION_FAILED", "READY_FOR_VALIDATION", "VALIDATING", "VALIDATION_FAILED",
      "READY_FOR_HUMAN_REVIEW", "HUMAN_VERIFIED", "REQUIRES_MANUAL_REVIEW"],
    failedStatuses: ["OCR_FAILED"],
  },
  {
    key: "chunk",
    label: "Chunk",
    icon: "✂️",
    activeStatuses: ["READY_FOR_CHUNKING", "CHUNKING"],
    doneStatuses: ["READY_FOR_EXTRACTION", "EXTRACTING", "EXTRACTION_FAILED",
      "READY_FOR_NORMALIZATION", "NORMALIZING", "NORMALIZATION_FAILED",
      "READY_FOR_VALIDATION", "VALIDATING", "VALIDATION_FAILED",
      "READY_FOR_HUMAN_REVIEW", "HUMAN_VERIFIED", "REQUIRES_MANUAL_REVIEW"],
    failedStatuses: ["CHUNKING_FAILED"],
  },
  {
    key: "extract",
    label: "Extract",
    icon: "🤖",
    activeStatuses: ["READY_FOR_EXTRACTION", "EXTRACTING"],
    doneStatuses: ["READY_FOR_NORMALIZATION", "NORMALIZING", "NORMALIZATION_FAILED",
      "READY_FOR_VALIDATION", "VALIDATING", "VALIDATION_FAILED",
      "READY_FOR_HUMAN_REVIEW", "HUMAN_VERIFIED", "REQUIRES_MANUAL_REVIEW"],
    failedStatuses: ["EXTRACTION_FAILED"],
  },
  {
    key: "normalize",
    label: "Normalize",
    icon: "⚙️",
    activeStatuses: ["READY_FOR_NORMALIZATION", "NORMALIZING"],
    doneStatuses: ["READY_FOR_VALIDATION", "VALIDATING", "VALIDATION_FAILED",
      "READY_FOR_HUMAN_REVIEW", "HUMAN_VERIFIED", "REQUIRES_MANUAL_REVIEW"],
    failedStatuses: ["NORMALIZATION_FAILED"],
  },
  {
    key: "validate",
    label: "Validate",
    icon: "✅",
    activeStatuses: ["READY_FOR_VALIDATION", "VALIDATING"],
    doneStatuses: ["READY_FOR_HUMAN_REVIEW", "READY_FOR_VERIFICATION", "PUBLISHED", "HUMAN_VERIFIED", "REQUIRES_MANUAL_REVIEW"],
    failedStatuses: ["VALIDATION_FAILED"],
  },
  {
    key: "publish",
    label: "Published",
    icon: "🚀",
    activeStatuses: ["READY_FOR_VERIFICATION", "READY_FOR_HUMAN_REVIEW"],
    doneStatuses: ["PUBLISHED", "HUMAN_VERIFIED", "ACTIVE"],
    failedStatuses: [],
  },
];

// ─── Stage state resolver ─────────────────────────────────────────────────────

type StageState = "done" | "active" | "failed" | "pending";

function getStageState(stage: PipelineStage, status: string): StageState {
  if (stage.failedStatuses.includes(status)) return "failed";
  if (stage.doneStatuses.includes(status)) return "done";
  if (stage.activeStatuses.includes(status)) return "active";
  return "pending";
}

// ─── Pipeline Progress component ─────────────────────────────────────────────

function PipelineProgress({ status }: { status: string }) {
  const isTerminal = ["DUPLICATE", "INVALID"].includes(status);
  const isVersion = status === "VERSION_REVIEW_REQUIRED";

  if (isTerminal) {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200">
        {status === "DUPLICATE" ? "⊘ Duplicate" : "✕ Invalid"}
      </span>
    );
  }
  if (isVersion) {
    return (
      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
        ⚡ Version Review
      </span>
    );
  }

  return (
    <div className="flex items-center gap-[3px]">
      {PIPELINE_STAGES.map((stage, idx) => {
        const state = getStageState(stage, status);
        return (
          <React.Fragment key={stage.key}>
            <PipelineStageNode stage={stage} state={state} />
            {idx < PIPELINE_STAGES.length - 1 && (
              <div
                className={`h-[2px] w-[10px] rounded-full transition-colors ${
                  state === "done" ? "bg-emerald-400" : "bg-slate-200"
                }`}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function PipelineStageNode({ stage, state }: { stage: PipelineStage; state: StageState }) {
  const baseClass =
    "relative flex items-center justify-center w-[26px] h-[26px] rounded-full text-[11px] font-bold border transition-all select-none overflow-hidden";

  const stateClass = {
    done: "bg-emerald-500 border-emerald-600 text-white shadow-sm",
    active: "bg-blue-600 border-blue-700 text-white shadow-md shadow-blue-200",
    failed: "bg-rose-500 border-rose-600 text-white shadow-sm",
    pending: "bg-slate-100 border-slate-200 text-slate-400",
  }[state];

  return (
    <div className={`${baseClass} ${stateClass}`} title={`${stage.label}: ${state.toUpperCase()}`}>
      {/* Shimmer animation for active stage */}
      {state === "active" && (
        <span className="absolute inset-0 overflow-hidden rounded-full pointer-events-none">
          <span
            className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/40 to-transparent"
            style={{ animationDuration: "1.4s", animationIterationCount: "infinite" }}
          />
        </span>
      )}
      {/* Pulsing ring for active */}
      {state === "active" && (
        <span className="absolute inset-0 rounded-full animate-ping bg-blue-400 opacity-30 pointer-events-none" />
      )}
      <span className="relative z-10 text-[10px]">
        {state === "done" ? "✓" : state === "failed" ? "✕" : stage.icon}
      </span>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AdminDocumentsPage() {
  const [documents, setDocuments] = useState<AdminDocumentListItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(20);

  const [statusFilter, setStatusFilter] = useState<string>("");
  const [methodFilter, setMethodFilter] = useState<string>("");
  const [failedOnly, setFailedOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const [showUpload, setShowUpload] = useState<boolean>(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTitle, setUploadTitle] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);

  // Auto-refresh every 6s when documents are actively processing
  const hasActiveDocuments = documents.some((d) =>
    ["READY_FOR_DUPLICATE_CHECK", "DUPLICATE_CHECKING", "READY_FOR_PARSING", "PARSING",
     "READY_FOR_OCR_CHECK", "OCR_CHECKING", "READY_FOR_CHUNKING", "CHUNKING",
     "READY_FOR_EXTRACTION", "EXTRACTING", "READY_FOR_NORMALIZATION", "NORMALIZING",
     "READY_FOR_VALIDATION", "VALIDATING"].includes(d.processing_status)
  );

  const loadDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminDocuments({
        status: statusFilter || undefined,
        ingestion_method: methodFilter || undefined,
        failed_only: failedOnly ? true : undefined,
        query: searchQuery.trim() || undefined,
        page,
        page_size: pageSize,
      });
      setDocuments(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load documents:", err);
      setError(err.message || "Failed to load documents.");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, methodFilter, failedOnly, searchQuery, page, pageSize]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Watch Folder State
  const [watchFolder, setWatchFolder] = useState<WatchFolderStatus | null>(null);
  const [isScanningFolder, setIsScanningFolder] = useState<boolean>(false);

  const fetchWatchFolder = useCallback(async () => {
    try {
      const st = await getWatchFolderStatus();
      setWatchFolder(st);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchWatchFolder();
  }, [fetchWatchFolder]);

  // Auto-refresh poll when processing is active
  useEffect(() => {
    if (!hasActiveDocuments) return;
    const interval = setInterval(() => {
      loadDocuments();
      fetchWatchFolder();
    }, 6000);
    return () => clearInterval(interval);
  }, [hasActiveDocuments, loadDocuments, fetchWatchFolder]);

  const handleRetry = async (doc: AdminDocumentListItem) => {
    if (!doc.valid_retry_action) return;
    setRetryingId(doc.id);
    setActionNotice(null);
    try {
      const res = await retryAdminDocument(doc.id, doc.valid_retry_action);
      setActionNotice(`Document ${doc.document_code}: ${res.message}`);
      await loadDocuments();
    } catch (err: any) {
      setError(err.message || "Retry action failed.");
    } finally {
      setRetryingId(null);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;
    setIsUploading(true);
    try {
      const doc = await uploadDocument(uploadFile, uploadTitle);
      setActionNotice(`✅ ${doc.document_code} uploaded — pipeline running automatically.`);
      setUploadFile(null);
      setUploadTitle("");
      setShowUpload(false);
      await loadDocuments();
    } catch (err: any) {
      setError(err.message || "Document upload failed.");
    } finally {
      setIsUploading(false);
    }
  };

  const columns = [
    {
      header: "Document & Code",
      render: (d: AdminDocumentListItem) => (
        <div className="space-y-0.5">
          <div className="font-bold text-slate-900 text-[13px]">{d.original_filename}</div>
          <div className="text-[11px] font-mono text-slate-400">
            {d.document_code} {d.page_count ? `• ${d.page_count}pp` : ""}
          </div>
        </div>
      ),
    },
    {
      header: "Pipeline Progress",
      render: (d: AdminDocumentListItem) => (
        <div className="space-y-1.5">
          <PipelineProgress status={d.processing_status} />
          <div className="text-[10px] text-slate-400 font-mono">
            {d.processing_status}
          </div>
        </div>
      ),
    },
    {
      header: "Status",
      render: (d: AdminDocumentListItem) => (
        <div className="space-y-1">
          <StatusBadge status={d.processing_status} />
          {d.failure_reason && (
            <div className="text-[10px] text-rose-700 max-w-[180px] truncate" title={d.failure_reason}>
              {d.failure_reason}
            </div>
          )}
        </div>
      ),
    },
    {
      header: "Updated",
      render: (d: AdminDocumentListItem) => (
        <div className="text-[11px] text-slate-500 font-mono">
          {new Date(d.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          <div className="text-[10px] text-slate-400">
            {new Date(d.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
          </div>
        </div>
      ),
    },
    {
      header: "Action",
      render: (d: AdminDocumentListItem) => {
        if (!d.retry_valid || !d.valid_retry_action) {
          return (
            <span className="text-[11px] text-slate-400">
              {d.processing_status === "EXACT_DUPLICATE"
                ? "Terminal"
                : hasActiveDocuments
                ? "⏳ Running…"
                : "—"}
            </span>
          );
        }

        const isRetrying = retryingId === d.id;
        const retryLabel = d.valid_retry_action.replace(/_/g, " ").toLowerCase();

        return (
          <button
            onClick={() => handleRetry(d)}
            disabled={isRetrying}
            className="text-[11px] font-semibold text-rose-700 hover:text-rose-900 border border-rose-200 hover:border-rose-300 rounded px-2.5 py-1 bg-rose-50/60 hover:bg-rose-100 transition capitalize disabled:opacity-50"
          >
            {isRetrying ? "Retrying…" : retryLabel}
          </button>
        );
      },
    },
  ];

  return (
    <>
      {/* Global shimmer keyframe */}
      <style>{`
        @keyframes shimmer {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
        .animate-shimmer { animation: shimmer 1.4s infinite; }
      `}</style>

      <div className="space-y-5">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200">
          <div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Document Ingestion &amp; Pipeline
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Documents progress automatically through all stages after upload
            </p>
          </div>
          <div className="flex items-center gap-2">
            {hasActiveDocuments && (
              <span className="flex items-center gap-1.5 text-[11px] font-medium text-blue-700 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200 animate-pulse">
                <span className="w-1.5 h-1.5 bg-blue-500 rounded-full inline-block" />
                Pipeline Running
              </span>
            )}
            <button
              onClick={() => setShowUpload(true)}
              className="text-xs text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded font-medium shadow-sm transition"
            >
              + Upload Document
            </button>
            <button
              onClick={() => loadDocuments()}
              className="text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1.5 rounded bg-white border border-slate-300 hover:bg-slate-50 transition"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Watch Folder Hot-Drop Panel */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-base">📂</span>
              <span className="font-bold text-slate-800 text-xs">Automated Watch Folder (Hot Drop)</span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                🟢 Watching for PDFs &amp; Excel
              </span>
            </div>
            <p className="text-[11px] text-slate-500">
              Drop any Rajasthan government PDF or Excel circular (.pdf, .xlsx, .xls, .csv) into this directory. Files are automatically detected, ingested, parsed, and published directly to the database without requiring human verification.
            </p>
            <div className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-1 rounded inline-block">
              Path: {watchFolder?.folder_path || "storage/watch_folder"} {watchFolder?.pending_count ? `(${watchFolder.pending_count} pending)` : ""}
            </div>
          </div>

          <button
            type="button"
            onClick={async () => {
              setIsScanningFolder(true);
              try {
                const res = await scanWatchFolderNow();
                setActionNotice(`Watch folder scan complete: ${res.ingested_count} new file(s) ingested into direct pipeline.`);
                await fetchWatchFolder();
                await loadDocuments();
              } catch (err: any) {
                setError(err.message || "Failed scanning watch folder.");
              } finally {
                setIsScanningFolder(false);
              }
            }}
            disabled={isScanningFolder}
            className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition flex items-center gap-1.5 whitespace-nowrap self-stretch sm:self-auto justify-center"
          >
            {isScanningFolder ? (
              <>
                <span className="animate-spin text-sm">↻</span>
                <span>Scanning Folder...</span>
              </>
            ) : (
              <>
                <span>⚡</span>
                <span>Scan Watch Folder Now</span>
              </>
            )}
          </button>
        </div>

        {/* Stage Legend */}
        <div className="flex flex-wrap gap-3 text-[11px] bg-white rounded-lg border border-slate-200 p-3 shadow-sm">
          <span className="font-semibold text-slate-600 mr-1">Legend:</span>
          {[
            { color: "bg-emerald-500", label: "Done" },
            { color: "bg-blue-600 animate-pulse", label: "Active (shining)" },
            { color: "bg-rose-500", label: "Failed" },
            { color: "bg-slate-200", label: "Pending" },
          ].map((l) => (
            <span key={l.label} className="flex items-center gap-1">
              <span className={`w-3 h-3 rounded-full ${l.color}`} />
              {l.label}
            </span>
          ))}
          <span className="text-slate-400 ml-auto">
            {PIPELINE_STAGES.map((s) => s.label).join(" → ")}
          </span>
        </div>

        {actionNotice && (
          <div className="p-3 text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 rounded">
            {actionNotice}
          </div>
        )}
        {error && (
          <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-800 rounded">
            {error}
          </div>
        )}

        {/* Filters Bar */}
        <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm flex flex-wrap items-center gap-3 text-xs">
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search by code, filename, or title..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setPage(1); }}
              className="w-full h-8 px-2.5 bg-slate-50 border border-slate-300 rounded text-xs placeholder-slate-400 focus:outline-none focus:border-blue-500"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="h-8 px-2 bg-slate-50 border border-slate-300 rounded text-xs"
          >
            <option value="">All Statuses</option>
            <option value="READY_FOR_PARSING">Ready for Parsing</option>
            <option value="PARSING_FAILED">Parsing Failed</option>
            <option value="READY_FOR_OCR_CHECK">Ready for OCR</option>
            <option value="OCR_FAILED">OCR Failed</option>
            <option value="READY_FOR_EXTRACTION">Ready for Extraction</option>
            <option value="EXTRACTION_FAILED">Extraction Failed</option>
            <option value="READY_FOR_HUMAN_REVIEW">Ready for Review</option>
            <option value="HUMAN_VERIFIED">Verified</option>
            <option value="DUPLICATE">Duplicate</option>
          </select>
          <select
            value={methodFilter}
            onChange={(e) => { setMethodFilter(e.target.value); setPage(1); }}
            className="h-8 px-2 bg-slate-50 border border-slate-300 rounded text-xs"
          >
            <option value="">All Methods</option>
            <option value="MANUAL_UPLOAD">Manual Upload</option>
            <option value="MONITORING_CHANGE_DETECTION">Monitoring</option>
            <option value="AUTOMATED_CRAWL">Automated Crawl</option>
          </select>
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={failedOnly}
              onChange={(e) => { setFailedOnly(e.target.checked); setPage(1); }}
              className="rounded text-rose-600 focus:ring-0"
            />
            <span className="text-slate-700 font-medium">Failed only</span>
          </label>
        </div>

        {/* Documents Table */}
        <DataTable
          columns={columns}
          data={documents}
          isLoading={isLoading}
          emptyMessage="No documents match the specified criteria."
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={(p) => setPage(p)}
        />

        {/* Upload Modal */}
        {showUpload && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl border border-slate-200 shadow-2xl max-w-md w-full p-6 text-xs text-slate-800 space-y-4">
              <div className="flex items-center justify-between border-b pb-3">
                <div>
                  <h3 className="font-bold text-sm text-slate-900">Upload Government Document</h3>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    All 7 pipeline stages run automatically after upload
                  </p>
                </div>
                <button onClick={() => setShowUpload(false)} className="text-slate-400 hover:text-slate-600">
                  ✕
                </button>
              </div>

              {/* Auto-pipeline info */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="text-[11px] text-blue-800 font-semibold mb-1.5">
                  🚀 Auto-Pipeline Enabled
                </div>
                <div className="flex flex-wrap gap-1">
                  {PIPELINE_STAGES.map((s, i) => (
                    <React.Fragment key={s.key}>
                      <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">
                        {s.icon} {s.label}
                      </span>
                      {i < PIPELINE_STAGES.length - 1 && (
                        <span className="text-[10px] text-blue-400 self-center">→</span>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>

              <form onSubmit={handleUploadSubmit} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Optional Document Title
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Rajasthan Old Age Pension Circular 2026"
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    className="w-full h-8 px-2.5 bg-slate-50 border border-slate-300 rounded focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                    Select File (PDF, XLSX, XLS, CSV)
                  </label>
                  <input
                    type="file"
                    required
                    accept=".pdf,.xlsx,.xls,.csv"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="w-full text-slate-600 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
                  />
                </div>
                <div className="flex items-center justify-end gap-2 pt-2 border-t">
                  <button
                    type="button"
                    onClick={() => setShowUpload(false)}
                    className="px-3 py-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!uploadFile || isUploading}
                    className="px-4 py-1.5 rounded bg-blue-600 text-white font-semibold hover:bg-blue-700 disabled:opacity-50 transition"
                  >
                    {isUploading ? "Uploading…" : "🚀 Start Pipeline"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
