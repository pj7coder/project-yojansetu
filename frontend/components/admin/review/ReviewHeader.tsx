"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ReviewSessionDetail } from "../../../types/review";

interface ReviewHeaderProps {
  detail: ReviewSessionDetail;
  onComplete: (notes?: string) => Promise<void>;
  onReject: (reason: string) => Promise<void>;
  onReopen: (reason: string) => Promise<void>;
  isSubmitting: boolean;
}

export function ReviewHeader({
  detail,
  onComplete,
  onReject,
  onReopen,
  isSubmitting,
}: ReviewHeaderProps) {
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [completeNotes, setCompleteNotes] = useState("");
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [showReopenModal, setShowReopenModal] = useState(false);
  const [reopenReason, setReopenReason] = useState("");

  const totalItems = detail.summary.total_items || detail.items.length || 0;
  const pendingItems =
    detail.summary.pending ??
    detail.items.filter((i) => i.decision === "PENDING").length;
  const resolvedItems = totalItems - pendingItems;

  const blockerCount = detail.items.filter(
    (i) =>
      i.risk_level === "BLOCKER" ||
      (i.validation_issues_summary &&
        i.validation_issues_summary.some((v) => v.severity === "BLOCKER"))
  ).length;

  const unaddressedContradictions = detail.items.filter(
    (i) => i.verification_result === "CONTRADICTED" && i.decision === "PENDING"
  ).length;

  const canComplete =
    pendingItems === 0 &&
    blockerCount === 0 &&
    unaddressedContradictions === 0 &&
    !detail.is_stale &&
    detail.session_status !== "COMPLETED";

  const getStatusBadge = () => {
    switch (detail.draft_status) {
      case "HUMAN_VERIFIED":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            ✓ HUMAN VERIFIED
          </span>
        );
      case "HUMAN_REJECTED":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-300">
            ✕ HUMAN REJECTED
          </span>
        );
      case "IN_HUMAN_REVIEW":
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-300">
            ● IN REVIEW
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            ⚠ READY FOR REVIEW
          </span>
        );
    }
  };

  return (
    <header className="bg-white border-b border-slate-200 shadow-sm px-6 py-4">
      {/* Top Breadcrumb & Metadata */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-3">
        <div className="flex items-center gap-3">
          <Link
            href="/admin/review"
            className="text-xs font-medium text-slate-500 hover:text-slate-800 flex items-center gap-1 transition"
          >
            ← Back to Review Queue
          </Link>
          <span className="text-slate-300">|</span>
          <span className="text-xs font-mono text-slate-500">
            Draft: {detail.internal_scheme_code}
          </span>
          <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
            Rev. v{detail.review_version}
          </span>
          {detail.is_stale && (
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300 animate-pulse">
              ⚠ Canonical Hash Mismatch (Stale)
            </span>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {detail.draft_status === "HUMAN_VERIFIED" || detail.draft_status === "HUMAN_REJECTED" ? (
            <button
              type="button"
              onClick={() => setShowReopenModal(true)}
              disabled={isSubmitting}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 transition shadow-sm"
            >
              ↻ Reopen Review
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={() => setShowRejectModal(true)}
                disabled={isSubmitting}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white hover:bg-red-50 text-red-700 border border-red-200 hover:border-red-300 transition shadow-sm"
              >
                Reject Scheme
              </button>

              <button
                type="button"
                onClick={() => setShowCompleteModal(true)}
                disabled={!canComplete || isSubmitting}
                title={
                  !canComplete
                    ? `Cannot complete: ${pendingItems} pending items, ${blockerCount} blockers, ${unaddressedContradictions} unaddressed contradictions`
                    : "Finalize human verification and seal verified artifact"
                }
                className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-sm flex items-center gap-1.5"
              >
                ✓ Complete Verification
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Scheme Title & Risk Metrics */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              {detail.scheme_name}
            </h1>
            {getStatusBadge()}
          </div>
          <p className="text-xs text-slate-500 mt-1 flex items-center gap-2">
            <span>🏛 {detail.department_name || "Department of Social Justice & Empowerment"}</span>
            <span>•</span>
            <span>Reviewer: <strong className="text-slate-700">{detail.reviewer_id}</strong></span>
          </p>
        </div>

        {/* Progress & Issue Badges */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Progress Pill */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-center min-w-[120px]">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">
              Progress
            </div>
            <div className="text-sm font-bold text-slate-800">
              {resolvedItems} / {totalItems}{" "}
              <span className="text-xs font-normal text-slate-500">resolved</span>
            </div>
          </div>

          {/* Critical Blockers */}
          {blockerCount > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-1.5 text-center">
              <div className="text-[10px] uppercase tracking-wider text-red-500 font-bold">
                Blockers
              </div>
              <div className="text-sm font-bold text-red-700">{blockerCount}</div>
            </div>
          )}

          {/* Contradictions */}
          {unaddressedContradictions > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5 text-center">
              <div className="text-[10px] uppercase tracking-wider text-amber-600 font-bold">
                Contradictions
              </div>
              <div className="text-sm font-bold text-amber-800">
                {unaddressedContradictions}
              </div>
            </div>
          )}

          {/* Conflicts */}
          {detail.conflicts && detail.conflicts.length > 0 && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg px-3 py-1.5 text-center">
              <div className="text-[10px] uppercase tracking-wider text-purple-600 font-bold">
                Conflicts
              </div>
              <div className="text-sm font-bold text-purple-800">
                {detail.conflicts.length}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Complete Verification Modal */}
      {showCompleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-base font-bold text-slate-900 mb-2 flex items-center gap-2">
              ✓ Seal Human Verification
            </h3>
            <p className="text-xs text-slate-600 mb-4">
              All {totalItems} review facts have been reviewed and zero blockers remain.
              This will create the immutable verified artifact and transition status to{" "}
              <strong>HUMAN_VERIFIED</strong>.
            </p>
            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Reviewer Signoff Notes (Optional)
              </label>
              <textarea
                value={completeNotes}
                onChange={(e) => setCompleteNotes(e.target.value)}
                placeholder="Enter any auditing remarks..."
                rows={3}
                className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowCompleteModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  await onComplete(completeNotes);
                  setShowCompleteModal(false);
                }}
                disabled={isSubmitting}
                className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 transition"
              >
                Confirm & Seal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Scheme Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-base font-bold text-red-700 mb-2 flex items-center gap-2">
              ✕ Reject Scheme Draft
            </h3>
            <p className="text-xs text-slate-600 mb-4">
              Rejecting this draft flags it as <strong>HUMAN_REJECTED</strong>. The draft and
              its complete audit trail are preserved without deletion.
            </p>
            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Mandatory Rejection Reason *
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Why is this scheme being rejected? (e.g., Not a government scheme, duplicate, outside Rajasthan jurisdiction)"
                rows={3}
                required
                className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-red-500"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowRejectModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!rejectReason.trim()) return;
                  await onReject(rejectReason);
                  setShowRejectModal(false);
                }}
                disabled={!rejectReason.trim() || isSubmitting}
                className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 transition"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reopen Review Modal */}
      {showReopenModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-base font-bold text-slate-900 mb-2">
              ↻ Reopen Scheme Review
            </h3>
            <p className="text-xs text-slate-600 mb-4">
              A new review session version will be initiated. The prior completed review and
              its audit snapshot will be preserved permanently in history.
            </p>
            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Mandatory Reopening Reason *
              </label>
              <textarea
                value={reopenReason}
                onChange={(e) => setReopenReason(e.target.value)}
                placeholder="Reason for reopening (e.g. government amendment, policy correction)"
                rows={3}
                required
                className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowReopenModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  if (!reopenReason.trim()) return;
                  await onReopen(reopenReason);
                  setShowReopenModal(false);
                }}
                disabled={!reopenReason.trim() || isSubmitting}
                className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition"
              >
                Confirm Reopen
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
