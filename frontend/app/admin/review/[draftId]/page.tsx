"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  completeReview,
  getReviewDetail,
  rejectScheme,
  reopenReview,
  resolveConflict,
  submitItemDecision,
} from "../../../../lib/api";
import {
  ConflictItem,
  ConflictResolutionPayload,
  ItemDecisionPayload,
  ReviewSessionDetail,
} from "../../../../types/review";
import { PdfViewer } from "../../../../components/admin/review/PdfViewer";
import { ReviewHeader } from "../../../../components/admin/review/ReviewHeader";
import { ReviewItemCard } from "../../../../components/admin/review/ReviewItemCard";
import { ConflictReviewModal } from "../../../../components/admin/review/ConflictReviewModal";
import { AuditLogViewer } from "../../../../components/admin/review/AuditLogViewer";

export default function SchemeReviewWorkspacePage() {
  const params = useParams();
  const draftId = params?.draftId as string;

  const [detail, setDetail] = useState<ReviewSessionDetail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [targetPdfPage, setTargetPdfPage] = useState<number>(1);
  const [activeConflict, setActiveConflict] = useState<ConflictItem | null>(null);

  const fetchDetail = useCallback(async () => {
    if (!draftId) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await getReviewDetail(draftId);
      setDetail(data);
    } catch (err: any) {
      setError(err.message || "Failed to load review workspace detail.");
    } finally {
      setIsLoading(false);
    }
  }, [draftId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const handleDecision = async (itemId: string, payload: ItemDecisionPayload) => {
    if (!detail) return;
    setIsSubmitting(true);
    try {
      await submitItemDecision(itemId, payload, detail.review_version);
      // Reload workspace to update audit log, verification results, and revalidated statuses
      await fetchDetail();
    } catch (err: any) {
      alert(`Decision submission failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResolveConflict = async (
    conflictId: string,
    payload: ConflictResolutionPayload
  ) => {
    if (!draftId) return;
    setIsSubmitting(true);
    try {
      await resolveConflict(draftId, conflictId, payload);
      await fetchDetail();
    } catch (err: any) {
      alert(`Conflict resolution failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleComplete = async (notes?: string) => {
    if (!detail || !draftId) return;
    setIsSubmitting(true);
    try {
      await completeReview(draftId, {
        notes,
        review_version: detail.review_version,
      });
      await fetchDetail();
      alert("✓ Scheme draft successfully verified and sealed!");
    } catch (err: any) {
      alert(`Completion failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRejectScheme = async (reason: string) => {
    if (!draftId) return;
    setIsSubmitting(true);
    try {
      await rejectScheme(draftId, { reason });
      await fetchDetail();
      alert("✕ Scheme draft rejected.");
    } catch (err: any) {
      alert(`Scheme rejection failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReopen = async (reason: string) => {
    if (!draftId) return;
    setIsSubmitting(true);
    try {
      await reopenReview(draftId, { reason });
      await fetchDetail();
      alert("↻ Scheme review session reopened.");
    } catch (err: any) {
      alert(`Reopening failed: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-100 flex items-center justify-center p-6 text-xs text-slate-500">
        <div className="text-center space-y-2">
          <div className="animate-spin text-3xl">⚙</div>
          <div className="font-semibold text-slate-700">Loading Review Workspace...</div>
          <p className="text-slate-400">Loading canonical facts, PDF source, and validation reports...</p>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="min-h-screen bg-slate-100 p-8 flex items-center justify-center">
        <div className="bg-white border border-red-200 rounded-2xl p-6 max-w-md w-full text-center space-y-3 shadow-sm">
          <div className="text-3xl">⚠</div>
          <h2 className="text-base font-bold text-slate-900">Review Workspace Error</h2>
          <p className="text-xs text-red-700">{error || "Scheme draft not found"}</p>
          <button
            onClick={() => fetchDetail()}
            className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700"
          >
            Retry Loading
          </button>
        </div>
      </div>
    );
  }

  // Filter items by active section tab
  const filteredItems = detail.items.filter((item) => {
    if (activeTab === "all") return true;
    if (activeTab === "eligibility") return item.item_type === "ELIGIBILITY";
    if (activeTab === "exclusions") return item.item_type === "EXCLUSION";
    if (activeTab === "benefits") return item.item_type === "BENEFIT";
    if (activeTab === "documents") return item.item_type === "DOCUMENT";
    if (activeTab === "application") return item.item_type === "APPLICATION";
    return true;
  });

  // Sort high-risk items first
  const sortedItems = [...filteredItems].sort((a, b) => {
    const riskScore = (item: typeof a) => {
      if (item.risk_level === "BLOCKER") return 100;
      if (item.verification_result === "CONTRADICTED") return 90;
      if (item.ocr_risk) return 80;
      if (item.verification_result === "NOT_ENOUGH_EVIDENCE") return 70;
      if (item.risk_level === "HIGH") return 60;
      if (item.risk_level === "MEDIUM") return 50;
      return 10;
    };
    return riskScore(b) - riskScore(a);
  });

  return (
    <div className="h-screen flex flex-col bg-slate-100 overflow-hidden">
      {/* Top Review Header */}
      <ReviewHeader
        detail={detail}
        onComplete={handleComplete}
        onReject={handleRejectScheme}
        onReopen={handleReopen}
        isSubmitting={isSubmitting}
      />

      {/* Main Split-Screen Workspace */}
      <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
        {/* Left Side: Original PDF Viewer (50% desktop width) */}
        <div className="w-full lg:w-1/2 h-[45vh] lg:h-full p-3 lg:pr-1.5 flex flex-col">
          <PdfViewer
            documentId={detail.document_id}
            targetPage={targetPdfPage}
            filename={`${detail.internal_scheme_code}.pdf`}
          />
        </div>

        {/* Right Side: Review Facts & Decision Panel (50% desktop width) */}
        <div className="w-full lg:w-1/2 h-[55vh] lg:h-full p-3 lg:pl-1.5 flex flex-col overflow-hidden">
          <div className="bg-white border border-slate-200 rounded-xl shadow-xs flex-1 flex flex-col overflow-hidden">
            {/* Navigation Tabs */}
            <div className="flex items-center gap-1 px-4 pt-3 pb-2 border-b border-slate-200 bg-slate-50/70 overflow-x-auto text-xs">
              <button
                type="button"
                onClick={() => setActiveTab("all")}
                className={`px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap transition ${
                  activeTab === "all"
                    ? "bg-white text-blue-700 shadow-xs border border-slate-200"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                All Facts ({detail.items.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("eligibility")}
                className={`px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap transition ${
                  activeTab === "eligibility"
                    ? "bg-white text-blue-700 shadow-xs border border-slate-200"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Eligibility
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("exclusions")}
                className={`px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap transition ${
                  activeTab === "exclusions"
                    ? "bg-white text-blue-700 shadow-xs border border-slate-200"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Exclusions
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("benefits")}
                className={`px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap transition ${
                  activeTab === "benefits"
                    ? "bg-white text-blue-700 shadow-xs border border-slate-200"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Benefits
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("documents")}
                className={`px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap transition ${
                  activeTab === "documents"
                    ? "bg-white text-blue-700 shadow-xs border border-slate-200"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Documents
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("application")}
                className={`px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap transition ${
                  activeTab === "application"
                    ? "bg-white text-blue-700 shadow-xs border border-slate-200"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Application
              </button>

              {/* Conflicts Tab */}
              {detail.conflicts && detail.conflicts.length > 0 && (
                <button
                  type="button"
                  onClick={() => setActiveTab("conflicts")}
                  className={`px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap transition ${
                    activeTab === "conflicts"
                      ? "bg-purple-100 text-purple-900 shadow-xs border border-purple-300"
                      : "text-purple-700 hover:bg-purple-50"
                  }`}
                >
                  Conflicts ({detail.conflicts.length})
                </button>
              )}

              {/* Audit Log Tab */}
              <button
                type="button"
                onClick={() => setActiveTab("audit")}
                className={`px-3 py-1.5 rounded-lg font-semibold whitespace-nowrap transition ${
                  activeTab === "audit"
                    ? "bg-white text-blue-700 shadow-xs border border-slate-200"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Audit Trail ({detail.audit_events.length})
              </button>
            </div>

            {/* Content Body: Scrollable Fact List or Conflicts or Audit */}
            <div className="flex-1 p-4 overflow-y-auto space-y-3">
              {activeTab === "audit" ? (
                <AuditLogViewer events={detail.audit_events} />
              ) : activeTab === "conflicts" ? (
                <div className="space-y-3">
                  <h4 className="text-sm font-bold text-purple-900">
                    Candidate Extraction Contradictions & Version Conflicts
                  </h4>
                  {detail.conflicts.map((conf) => (
                    <div
                      key={conf.conflict_id}
                      className="border border-purple-200 bg-purple-50/40 rounded-xl p-4 flex items-center justify-between gap-4"
                    >
                      <div>
                        <div className="font-mono text-xs font-bold text-purple-950">
                          {conf.conflict_id}: {conf.field}
                        </div>
                        <p className="text-xs text-purple-800 mt-1">
                          {conf.explanation || "Conflicting extraction candidates detected across pages."}
                        </p>
                        <div className="text-[11px] text-purple-700 mt-1">
                          {conf.values.length} candidate values
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setActiveConflict(conf)}
                        className="px-3.5 py-1.5 rounded-lg text-xs font-bold text-white bg-purple-600 hover:bg-purple-700 shadow-xs transition"
                      >
                        Review Conflict →
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <>
                  {sortedItems.length === 0 ? (
                    <div className="p-8 text-center text-xs text-slate-500">
                      No facts found in this section.
                    </div>
                  ) : (
                    sortedItems.map((item) => (
                      <ReviewItemCard
                        key={item.id}
                        item={item}
                        reviewVersion={detail.review_version}
                        onSelectPage={(pageNum) => setTargetPdfPage(pageNum)}
                        onDecision={handleDecision}
                        isSubmitting={isSubmitting}
                      />
                    ))
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Conflict Review Modal Trigger */}
      {activeConflict && (
        <ConflictReviewModal
          conflict={activeConflict}
          onResolve={handleResolveConflict}
          onClose={() => setActiveConflict(null)}
          onSelectPage={(pageNum) => setTargetPdfPage(pageNum)}
          isSubmitting={isSubmitting}
        />
      )}
    </div>
  );
}
