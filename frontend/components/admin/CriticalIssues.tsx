"use client";

import React from "react";
import Link from "next/link";
import { CriticalIssue } from "../../types/admin";
import { StatusBadge } from "./StatusBadge";

interface CriticalIssuesProps {
  issues: CriticalIssue[];
}

export function CriticalIssues({ issues }: CriticalIssuesProps) {
  if (!issues || issues.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center gap-2 text-emerald-700 text-xs font-semibold">
          <span>✓</span>
          <span>No critical operational blockers or contradictions detected across subsystems.</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-rose-200 shadow-sm p-5">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-rose-100">
        <div className="flex items-center gap-2">
          <span className="text-base">🚨</span>
          <h2 className="text-sm font-bold text-slate-900 tracking-tight">
            Critical Issues & Blockers ({issues.length})
          </h2>
        </div>
        <span className="text-[11px] font-medium text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
          Requires Operator Action
        </span>
      </div>

      <div className="divide-y divide-slate-100">
        {issues.map((issue) => (
          <div
            key={issue.id}
            className="py-3 first:pt-0 last:pb-0 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <StatusBadge status={issue.severity} size="sm" />
                <span className="text-xs font-semibold text-slate-900">
                  {issue.title}
                </span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                  {issue.category}
                </span>
              </div>
              <p className="text-xs text-slate-600 max-w-3xl">
                {issue.description}
              </p>
            </div>

            <Link
              href={issue.link}
              className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800 flex-shrink-0"
            >
              <span>Resolve</span>
              <span>→</span>
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
