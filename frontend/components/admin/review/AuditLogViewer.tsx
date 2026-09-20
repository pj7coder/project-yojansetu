"use client";

import React from "react";
import { ReviewAuditEvent } from "../../../types/review";

interface AuditLogViewerProps {
  events: ReviewAuditEvent[];
}

export function AuditLogViewer({ events }: AuditLogViewerProps) {
  if (!events || events.length === 0) {
    return (
      <div className="p-6 text-center text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-xl">
        No audit events recorded yet for this review session.
      </div>
    );
  }

  const getActionBadge = (actionType: string) => {
    switch (actionType) {
      case "SCHEME_APPROVED":
        return "bg-emerald-100 text-emerald-800 border-emerald-300";
      case "SCHEME_REJECTED":
        return "bg-red-100 text-red-800 border-red-300";
      case "FIELD_EDITED":
        return "bg-blue-100 text-blue-800 border-blue-300";
      case "FIELD_REJECTED":
        return "bg-rose-100 text-rose-800 border-rose-300";
      case "CONFLICT_RESOLVED":
        return "bg-purple-100 text-purple-800 border-purple-300";
      case "VERIFICATION_OVERRIDE":
        return "bg-amber-100 text-amber-900 border-amber-300";
      default:
        return "bg-slate-100 text-slate-700 border-slate-300";
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          📜 Immutable Review Audit Log ({events.length})
        </h4>
        <span className="text-[11px] text-slate-500 font-mono">
          Cryptographically sealed trail
        </span>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
        {events.map((evt) => (
          <div
            key={evt.id}
            className="p-3 bg-slate-50/70 border border-slate-200 rounded-lg text-xs space-y-2 hover:bg-slate-50 transition"
          >
            {/* Header: Action type, field path, reviewer, timestamp */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`px-2 py-0.5 rounded-full text-[11px] font-bold border ${getActionBadge(
                    evt.action_type
                  )}`}
                >
                  {evt.action_type}
                </span>
                {evt.field_path && (
                  <span className="font-mono text-slate-700 font-semibold">
                    {evt.field_path}
                  </span>
                )}
              </div>
              <div className="text-[11px] text-slate-500">
                <strong>{evt.reviewer_id}</strong> •{" "}
                {new Date(evt.created_at).toLocaleString()}
              </div>
            </div>

            {/* Audit Reason */}
            {evt.reason && (
              <div className="text-slate-800 font-medium">
                <span className="text-slate-500 text-[11px]">Reason: </span>
                {evt.reason}
              </div>
            )}

            {/* Before / After Diff comparison */}
            {(evt.before_value_json || evt.after_value_json) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1">
                {evt.before_value_json && (
                  <div className="bg-red-50/50 border border-red-200 rounded p-2 text-red-900 font-mono">
                    <span className="text-[10px] font-bold uppercase text-red-700 block mb-0.5">
                      Before
                    </span>
                    <pre className="whitespace-pre-wrap break-all">
                      {JSON.stringify(evt.before_value_json)}
                    </pre>
                  </div>
                )}
                {evt.after_value_json && (
                  <div className="bg-emerald-50/50 border border-emerald-200 rounded p-2 text-emerald-900 font-mono">
                    <span className="text-[10px] font-bold uppercase text-emerald-700 block mb-0.5">
                      After
                    </span>
                    <pre className="whitespace-pre-wrap break-all">
                      {JSON.stringify(evt.after_value_json)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
