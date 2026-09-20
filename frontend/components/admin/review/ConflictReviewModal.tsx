"use client";

import React, { useState } from "react";
import { ConflictItem, ConflictResolutionChoice, ConflictResolutionPayload } from "../../../types/review";

interface ConflictReviewModalProps {
  conflict: ConflictItem;
  onResolve: (conflictId: string, payload: ConflictResolutionPayload) => Promise<void>;
  onClose: () => void;
  onSelectPage: (page: number) => void;
  isSubmitting: boolean;
}

export function ConflictReviewModal({
  conflict,
  onResolve,
  onClose,
  onSelectPage,
  isSubmitting,
}: ConflictReviewModalProps) {
  const [selectedChoice, setSelectedChoice] = useState<ConflictResolutionChoice>("SELECT_VALUE");
  const [selectedIdx, setSelectedIdx] = useState<number>(0);
  const [reason, setReason] = useState<string>("");

  const candidates = conflict.values || [];

  const handleResolveSubmit = async () => {
    if (!reason.trim()) return;

    let selectedVal: any = undefined;
    if (selectedChoice === "SELECT_VALUE" && candidates[selectedIdx]) {
      selectedVal = candidates[selectedIdx].value;
    }

    await onResolve(conflict.conflict_id, {
      choice: selectedChoice,
      selected_value: selectedVal,
      reason: reason.trim(),
    });

    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4">
      <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-2xl w-full p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div>
            <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
              ⚖ Resolve Extraction Conflict
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Conflict ID: <span className="font-mono font-semibold">{conflict.conflict_id}</span> • Field:{" "}
              <strong className="text-slate-800">{conflict.field}</strong>
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {conflict.explanation && (
          <div className="p-2.5 bg-purple-50 border border-purple-200 rounded-lg text-xs text-purple-900">
            <strong>Conflict Context:</strong> {conflict.explanation}
          </div>
        )}

        {/* Side-by-side Candidate Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {candidates.map((cand, idx) => (
            <div
              key={idx}
              onClick={() => {
                setSelectedChoice("SELECT_VALUE");
                setSelectedIdx(idx);
              }}
              className={`border-2 rounded-xl p-3.5 cursor-pointer transition ${
                selectedChoice === "SELECT_VALUE" && selectedIdx === idx
                  ? "border-blue-600 bg-blue-50/50 shadow-sm"
                  : "border-slate-200 hover:border-slate-300 bg-white"
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-slate-800">
                  Candidate {String.fromCharCode(65 + idx)}
                </span>
                {cand.page_number && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectPage(cand.page_number!);
                    }}
                    className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-100 hover:bg-blue-200 text-blue-800 transition"
                  >
                    Jump to Page {cand.page_number} ↗
                  </button>
                )}
              </div>

              {/* Value display */}
              <div className="bg-white border border-slate-200 rounded p-2 text-xs font-mono font-bold text-slate-900 mb-2">
                {JSON.stringify(cand.value)}
              </div>

              {/* Text snippet */}
              {cand.text_snippet && (
                <p className="text-xs text-slate-600 italic font-serif line-clamp-3">
                  "{cand.text_snippet}"
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Choice Radio / Selector */}
        <div className="space-y-2 border-t border-slate-200 pt-3">
          <label className="block text-xs font-bold text-slate-800 mb-1">
            Reviewer Resolution Decision
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
            <label
              className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer ${
                selectedChoice === "SELECT_VALUE"
                  ? "bg-blue-50 border-blue-500 font-bold text-blue-900"
                  : "border-slate-200 text-slate-700"
              }`}
            >
              <input
                type="radio"
                name="choice"
                checked={selectedChoice === "SELECT_VALUE"}
                onChange={() => setSelectedChoice("SELECT_VALUE")}
              />
              <span>Select Candidate {String.fromCharCode(65 + selectedIdx)}</span>
            </label>

            <label
              className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer ${
                selectedChoice === "KEEP_CONDITIONAL"
                  ? "bg-purple-50 border-purple-500 font-bold text-purple-900"
                  : "border-slate-200 text-slate-700"
              }`}
            >
              <input
                type="radio"
                name="choice"
                checked={selectedChoice === "KEEP_CONDITIONAL"}
                onChange={() => setSelectedChoice("KEEP_CONDITIONAL")}
              />
              <span>Keep Both (Conditional)</span>
            </label>

            <label
              className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer ${
                selectedChoice === "REJECT_FIELD"
                  ? "bg-red-50 border-red-500 font-bold text-red-900"
                  : "border-slate-200 text-slate-700"
              }`}
            >
              <input
                type="radio"
                name="choice"
                checked={selectedChoice === "REJECT_FIELD"}
                onChange={() => setSelectedChoice("REJECT_FIELD")}
              />
              <span>Reject Field Fact</span>
            </label>
          </div>
        </div>

        {/* Mandatory Reason */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Mandatory Conflict Audit Rationale *
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Official rationale for choosing this value or keeping both conditional branches..."
            rows={2}
            required
            className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Footer Actions */}
        <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleResolveSubmit}
            disabled={!reason.trim() || isSubmitting}
            className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition shadow-sm"
          >
            Resolve & Save
          </button>
        </div>
      </div>
    </div>
  );
}
