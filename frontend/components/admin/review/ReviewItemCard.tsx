"use client";

import React, { useState } from "react";
import { HumanReviewItem, ItemDecisionPayload } from "../../../types/review";

interface ReviewItemCardProps {
  item: HumanReviewItem;
  reviewVersion: number;
  onSelectPage: (page: number) => void;
  onDecision: (itemId: string, payload: ItemDecisionPayload) => Promise<void>;
  isSubmitting: boolean;
}

export function ReviewItemCard({
  item,
  reviewVersion,
  onSelectPage,
  onDecision,
  isSubmitting,
}: ReviewItemCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editText, setEditText] = useState(() =>
    JSON.stringify(item.current_value_json || item.original_value_json || {}, null, 2)
  );
  const [editReason, setEditReason] = useState("");

  const [showApproveModal, setShowApproveModal] = useState(false);
  const [approveComment, setApproveComment] = useState("");
  const [overrideReason, setOverrideReason] = useState("");

  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectComment, setRejectComment] = useState("");

  const isContradicted = item.verification_result === "CONTRADICTED";
  const isInsufficient = item.verification_result === "NOT_ENOUGH_EVIDENCE";
  const requiresOverride = isContradicted || isInsufficient;

  const handleApproveSubmit = async () => {
    if (requiresOverride && !overrideReason.trim()) return;
    await onDecision(item.id, {
      decision: "APPROVED",
      reviewer_comment: approveComment.trim() || undefined,
      override_reason: requiresOverride ? overrideReason.trim() : undefined,
    });
    setShowApproveModal(false);
  };

  const handleEditSubmit = async () => {
    if (!editReason.trim()) return;
    try {
      const parsedValue = JSON.parse(editText);
      await onDecision(item.id, {
        decision: "EDITED",
        edit_value: parsedValue,
        edit_reason: editReason.trim(),
      });
      setIsEditing(false);
    } catch {
      alert("Invalid JSON format. Please verify the edited value syntax.");
    }
  };

  const handleRejectSubmit = async () => {
    await onDecision(item.id, {
      decision: "REJECTED",
      reviewer_comment: rejectComment.trim() || undefined,
    });
    setShowRejectModal(false);
  };

  const handleNotApplicable = async () => {
    await onDecision(item.id, {
      decision: "NOT_APPLICABLE",
      reviewer_comment: "Marked not applicable by reviewer.",
    });
  };

  return (
    <div
      className={`border rounded-xl p-4 transition-all shadow-sm ${
        item.decision === "APPROVED"
          ? "bg-emerald-50/30 border-emerald-200"
          : item.decision === "EDITED"
          ? "bg-blue-50/30 border-blue-200"
          : item.decision === "REJECTED"
          ? "bg-red-50/30 border-red-200 opacity-75"
          : item.decision === "NOT_APPLICABLE"
          ? "bg-slate-50 border-slate-200 opacity-70"
          : isContradicted
          ? "bg-red-50/40 border-red-300"
          : "bg-white border-slate-200 hover:border-slate-300"
      }`}
    >
      {/* Top Bar: Field Path, Type & Badges */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-100">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
            {item.field_path}
          </span>
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wide">
            {item.item_type}
          </span>

          {/* Verification Badge */}
          {item.verification_result === "SUPPORTED" && (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
              ✓ SUPPORTED
            </span>
          )}
          {item.verification_result === "CONTRADICTED" && (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-800 border border-red-300 animate-pulse">
              ⚠ CONTRADICTED
            </span>
          )}
          {item.verification_result === "NOT_ENOUGH_EVIDENCE" && (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
              ? INSUFFICIENT EVIDENCE
            </span>
          )}

          {/* OCR Risk Badge */}
          {item.ocr_risk && (
            <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-orange-100 text-orange-900 border border-orange-300">
              🔍 OCR RISK
            </span>
          )}
        </div>

        {/* Decision Badge */}
        <div>
          {item.decision === "APPROVED" && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-600 text-white shadow-xs">
              ✓ APPROVED
            </span>
          )}
          {item.decision === "EDITED" && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-600 text-white shadow-xs">
              ✎ EDITED
            </span>
          )}
          {item.decision === "REJECTED" && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-600 text-white shadow-xs">
              ✕ REJECTED
            </span>
          )}
          {item.decision === "NOT_APPLICABLE" && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-500 text-white shadow-xs">
              N/A
            </span>
          )}
          {item.decision === "PENDING" && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-300">
              PENDING REVIEW
            </span>
          )}
        </div>
      </div>

      {/* Prominent OCR Warning */}
      {item.ocr_risk && (
        <div className="mt-2.5 p-2 bg-orange-50 border border-orange-200 rounded-lg text-xs text-orange-900 flex items-start gap-2">
          <span className="text-base leading-none">⚠</span>
          <div>
            <strong>OCR-derived numeric evidence:</strong> The extracted numbers rely on OCR
            transcription. Inspect the original government PDF page carefully before confirming.
          </div>
        </div>
      )}

      {/* Prominent Contradiction Warning */}
      {isContradicted && (
        <div className="mt-2.5 p-2.5 bg-red-50 border border-red-300 rounded-lg text-xs text-red-900 flex items-start gap-2">
          <span className="text-base leading-none">🚫</span>
          <div>
            <strong>Contradiction Detected (Day 12):</strong> The canonical value contradicts the cited
            government evidence snippet. You must either <em>EDIT</em> the canonical value to match the
            text or provide an explicit <em>OVERRIDE REASON</em> with supporting audit context.
          </div>
        </div>
      )}

      {/* Validation Issue Alerts */}
      {item.validation_issues_summary && item.validation_issues_summary.length > 0 && (
        <div className="mt-2.5 space-y-1">
          {item.validation_issues_summary.map((issue, idx) => (
            <div
              key={idx}
              className={`p-2 rounded-lg text-xs flex items-start gap-2 ${
                issue.severity === "BLOCKER"
                  ? "bg-red-100 text-red-900 border border-red-300 font-medium"
                  : issue.severity === "ERROR"
                  ? "bg-orange-100 text-orange-900 border border-orange-300"
                  : "bg-amber-50 text-amber-900 border border-amber-200"
              }`}
            >
              <span className="font-bold text-[10px] px-1 rounded bg-white/70">
                {issue.severity}
              </span>
              <span>
                <strong>{issue.rule_code}:</strong> {issue.message}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Main Fact Statement */}
      <div className="mt-3">
        <h4 className="text-sm font-semibold text-slate-900 leading-snug">
          {item.statement}
        </h4>
      </div>

      {/* Fact Comparison Grid: Canonical vs Raw vs Source Evidence */}
      <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
        {/* Canonical Value */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1">
            Canonical Value
          </div>
          <pre className="text-xs font-mono text-slate-800 whitespace-pre-wrap break-words overflow-x-auto max-h-36">
            {JSON.stringify(item.current_value_json || item.original_value_json, null, 2)}
          </pre>
          {item.edit_reason && (
            <div className="mt-2 pt-2 border-t border-slate-200 text-[11px] text-blue-700">
              <strong>Edit note:</strong> {item.edit_reason}
            </div>
          )}
        </div>

        {/* Raw Extracted Text */}
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-1">
            Raw Extraction (Llama)
          </div>
          <p className="text-xs text-slate-700 italic break-words line-clamp-6">
            {item.raw_text ? `"${item.raw_text}"` : "— Not captured —"}
          </p>
        </div>

        {/* Government Evidence Snippet */}
        <div className="bg-blue-50/50 border border-blue-200 rounded-lg p-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-1 mb-1">
              <span className="text-[10px] uppercase tracking-wider text-blue-800 font-bold">
                Source Evidence
              </span>
              {item.page_number && (
                <button
                  type="button"
                  onClick={() => onSelectPage(item.page_number!)}
                  className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-600 hover:bg-blue-700 text-white shadow-2xs transition"
                  title="Click to jump PDF viewer to this page"
                >
                  Jump to Page {item.page_number} ↗
                </button>
              )}
            </div>
            <p className="text-xs text-blue-950 break-words leading-relaxed font-serif line-clamp-5">
              {item.evidence_text ? `"${item.evidence_text}"` : "— No evidence cited —"}
            </p>
          </div>

          {item.block_id && (
            <div className="text-[10px] font-mono text-blue-600 mt-2">
              Block: {item.block_id}
            </div>
          )}
        </div>
      </div>

      {/* Inline Structured Editing Form */}
      {isEditing && (
        <div className="mt-3 p-3 bg-blue-50/60 border border-blue-300 rounded-xl space-y-3">
          <div className="flex items-center justify-between">
            <h5 className="text-xs font-bold text-blue-950">
              ✎ Edit Canonical Fact Value
            </h5>
            <span className="text-[11px] text-blue-700">
              Saving will recompute SHA-256 and trigger automatic revalidation & reverification.
            </span>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">
              Canonical JSON Data
            </label>
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              rows={4}
              className="w-full font-mono text-xs p-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-700 mb-1">
              Mandatory Edit Reason *
            </label>
            <input
              type="text"
              value={editReason}
              onChange={(e) => setEditReason(e.target.value)}
              placeholder="Why are you changing this value? (e.g., Corrected income limit from 3L to 2L based on Page 7 clause 3)"
              className="w-full text-xs p-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            />
          </div>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsEditing(false)}
              className="px-3 py-1 rounded text-xs font-medium text-slate-600 hover:bg-slate-200"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleEditSubmit}
              disabled={!editReason.trim() || isSubmitting}
              className="px-4 py-1 rounded text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition shadow-sm"
            >
              Save & Revalidate
            </button>
          </div>
        </div>
      )}

      {/* Reviewer Action Buttons */}
      {!isEditing && (
        <div className="mt-3.5 pt-2.5 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
          <div className="text-[11px] text-slate-500">
            {item.reviewed_by && (
              <span>
                Reviewed by <strong>{item.reviewed_by}</strong> at{" "}
                {new Date(item.reviewed_at!).toLocaleString()}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Not Applicable */}
            <button
              type="button"
              onClick={handleNotApplicable}
              disabled={isSubmitting}
              className="px-2.5 py-1 rounded text-xs font-medium text-slate-600 hover:bg-slate-100 border border-slate-200 transition"
              title="Fact is not applicable to this scheme"
            >
              N/A
            </button>

            {/* Reject Fact */}
            <button
              type="button"
              onClick={() => setShowRejectModal(true)}
              disabled={isSubmitting}
              className="px-2.5 py-1 rounded text-xs font-semibold text-red-700 hover:bg-red-50 border border-red-200 transition"
            >
              Reject Fact
            </button>

            {/* Edit Fact */}
            <button
              type="button"
              onClick={() => setIsEditing(true)}
              disabled={isSubmitting}
              className="px-3 py-1 rounded text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-300 transition"
            >
              ✎ Edit Value
            </button>

            {/* Approve Fact */}
            <button
              type="button"
              onClick={() => setShowApproveModal(true)}
              disabled={isSubmitting}
              className={`px-3.5 py-1 rounded text-xs font-bold text-white transition shadow-sm ${
                requiresOverride
                  ? "bg-amber-600 hover:bg-amber-700"
                  : "bg-emerald-600 hover:bg-emerald-700"
              }`}
            >
              {requiresOverride ? "⚠ Override & Approve" : "✓ Approve"}
            </button>
          </div>
        </div>
      )}

      {/* Approve / Override Modal */}
      {showApproveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-base font-bold text-slate-900 mb-2">
              {requiresOverride ? "⚠ Override & Approve Fact" : "✓ Approve Fact"}
            </h3>

            {requiresOverride ? (
              <div className="p-2.5 bg-amber-50 border border-amber-300 rounded-lg text-xs text-amber-900 mb-4">
                This fact has verification status: <strong>{item.verification_result}</strong>.
                An explicit override reason is mandatory to approve this field into official audit records.
              </div>
            ) : (
              <p className="text-xs text-slate-600 mb-4">
                Confirm approval of <strong>{item.field_path}</strong>.
              </p>
            )}

            {requiresOverride && (
              <div className="mb-3">
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Mandatory Override Reason *
                </label>
                <textarea
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="Explain why this fact is valid despite automated verification result..."
                  rows={2}
                  required
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>
            )}

            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Optional Reviewer Comment
              </label>
              <input
                type="text"
                value={approveComment}
                onChange={(e) => setApproveComment(e.target.value)}
                placeholder="Optional remark"
                className="w-full text-xs p-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowApproveModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleApproveSubmit}
                disabled={(requiresOverride && !overrideReason.trim()) || isSubmitting}
                className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 transition"
              >
                Confirm Approval
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-base font-bold text-red-700 mb-2">
              ✕ Reject Fact
            </h3>
            <p className="text-xs text-slate-600 mb-4">
              Rejecting this fact will exclude it from the final verified canonical scheme artifact.
              The original extracted fact and rejection reason will remain permanently in audit logs.
            </p>

            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Rejection Rationale (Recommended)
              </label>
              <textarea
                value={rejectComment}
                onChange={(e) => setRejectComment(e.target.value)}
                placeholder="Why is this fact being rejected? (e.g., Clause repealed, extraneous rule)"
                rows={2}
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
                onClick={handleRejectSubmit}
                disabled={isSubmitting}
                className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-red-600 hover:bg-red-700 transition"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
