"use client";

import React from "react";

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, size = "sm" }: StatusBadgeProps) {
  const norm = (status || "").toUpperCase();

  let bg = "bg-slate-100 text-slate-700 border-slate-300";
  let dot = "bg-slate-500";
  let label = status;
  let icon = "•";

  if (["HEALTHY", "ACTIVE", "SUCCESS", "HUMAN_VERIFIED", "PRODUCTION", "RESOLVED", "UNCHANGED"].includes(norm)) {
    bg = "bg-emerald-50 text-emerald-800 border-emerald-300";
    dot = "bg-emerald-500";
    icon = "✓";
  } else if (["WARNING", "DEGRADED", "CHANGED", "PENDING", "REVIEW_REQUIRED", "WAITING", "POSSIBLY_STUCK", "NOT_YET_ACTIVE"].includes(norm)) {
    bg = "bg-amber-50 text-amber-800 border-amber-300";
    dot = "bg-amber-500";
    icon = "⚠";
  } else if (["CRITICAL", "FAILED", "ERROR", "UNAVAILABLE", "CONTRADICTED", "CHECK_FAILED", "BLOCKED"].includes(norm)) {
    bg = "bg-rose-50 text-rose-800 border-rose-300";
    dot = "bg-rose-500";
    icon = "✕";
  } else if (["DISABLED", "INACTIVE", "ARCHIVED", "SUPERSEDED", "EXPIRED"].includes(norm)) {
    bg = "bg-slate-100 text-slate-600 border-slate-300";
    dot = "bg-slate-400";
    icon = "○";
  } else if (["EMPTY", "NEVER_CHECKED", "UNCHECKED", "UNKNOWN"].includes(norm)) {
    bg = "bg-sky-50 text-sky-800 border-sky-300";
    dot = "bg-sky-500";
    icon = "—";
  }

  const pad = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium border rounded-full ${pad} ${bg}`}
      title={`Status: ${status}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} aria-hidden="true" />
      <span className="font-semibold text-[11px]" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </span>
  );
}
