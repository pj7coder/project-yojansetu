"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getAdminOverview, getAdminActivity } from "../../lib/api";
import { AdminOverviewResponse, AdminActivityItem } from "../../types/admin";

export default function AdminOverviewPage() {
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [activities, setActivities] = useState<AdminActivityItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [ovData, actData] = await Promise.all([
        getAdminOverview(),
        getAdminActivity(8),
      ]);
      setOverview(ovData);
      setActivities(actData.items || []);
    } catch (err: any) {
      console.error("Dashboard overview load error:", err);
      setError(err.message || "Failed to load dashboard overview.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (isLoading && !overview) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-xs text-slate-500 gap-2 py-24">
        <span className="text-2xl animate-spin">⚙️</span>
        <span className="font-semibold text-slate-700">Loading operations dashboard...</span>
      </div>
    );
  }

  if (error && !overview) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-center text-xs max-w-lg mx-auto my-12">
        <div className="text-rose-800 font-bold mb-1">Unable to load dashboard overview</div>
        <div className="text-rose-600 mb-3">{error}</div>
        <button
          onClick={loadData}
          className="px-4 py-1.5 rounded-lg bg-rose-600 text-white font-medium hover:bg-rose-700 transition"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  if (!overview) return null;

  return (
    <div className="flex flex-col gap-3 h-full max-w-full">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between pb-1 border-b border-slate-200">
        <div className="flex items-center gap-2.5">
          <h1 className="text-lg font-black text-slate-900 tracking-tight">
            🇮🇳 National & State Operations Control
          </h1>
          <span
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold ${
              overview.system_status === "HEALTHY"
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : overview.system_status === "WARNING"
                ? "bg-amber-50 text-amber-700 border border-amber-200"
                : "bg-rose-50 text-rose-700 border border-rose-200"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                overview.system_status === "HEALTHY"
                  ? "bg-emerald-500 animate-pulse"
                  : overview.system_status === "WARNING"
                  ? "bg-amber-500"
                  : "bg-rose-500"
              }`}
            />
            {overview.system_status}
          </span>
          <span className="hidden md:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
            <span>🌐</span>
            <span>Live Data Sync (Port 8000)</span>
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span>Synced: {new Date(overview.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
          <button
            onClick={loadData}
            title="Refresh metrics from backend"
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs transition cursor-pointer"
          >
            <span>🔄</span>
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Row (5 Compact Tiles) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
        {/* Metric 1: Sources */}
        <Link
          href="/admin/sources"
          className="bg-white p-2.5 rounded-xl border border-slate-200 hover:border-slate-300 hover:shadow-xs transition group"
        >
          <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold">
            <span>Sources</span>
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-black text-slate-900">{overview.sources.active}</span>
            <span className="text-[11px] text-slate-400 font-medium">/ {overview.sources.total} active</span>
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5 truncate">
            {overview.sources.failing > 0 ? (
              <span className="text-rose-600 font-semibold">{overview.sources.failing} failing</span>
            ) : (
              <span>All sources responding</span>
            )}
          </div>
        </Link>

        {/* Metric 2: Documents */}
        <Link
          href="/admin/documents"
          className="bg-white p-2.5 rounded-xl border border-slate-200 hover:border-slate-300 hover:shadow-xs transition group"
        >
          <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold">
            <span>Documents</span>
            <span className="w-2 h-2 rounded-full bg-sky-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-black text-slate-900">{overview.documents.total}</span>
            <span className="text-[11px] text-slate-400 font-medium">ingested</span>
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5 truncate">
            {overview.documents.failed > 0 ? (
              <span className="text-rose-600 font-semibold">{overview.documents.failed} failed</span>
            ) : (
              <span>{overview.documents.processing} currently processing</span>
            )}
          </div>
        </Link>

        {/* Metric 3: Verified Schemes */}
        <Link
          href="/admin/schemes"
          className="bg-white p-2.5 rounded-xl border border-slate-200 hover:border-slate-300 hover:shadow-xs transition group"
        >
          <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold">
            <span>Verified Schemes</span>
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className="text-xl font-black text-emerald-600">{overview.schemes.human_verified}</span>
            <span className="text-[11px] text-slate-400 font-medium">/ {overview.schemes.total} total</span>
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {overview.schemes.active_versions} active versions
          </div>
        </Link>

        {/* Metric 4: Pending Reviews */}
        <Link
          href="/admin/review"
          className="bg-white p-2.5 rounded-xl border border-slate-200 hover:border-slate-300 hover:shadow-xs transition group"
        >
          <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold">
            <span>Pending Review</span>
            <span className={`w-2 h-2 rounded-full ${overview.reviews.critical > 0 ? 'bg-amber-500' : 'bg-slate-300'}`} />
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className={`text-xl font-black ${overview.reviews.critical > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
              {overview.reviews.pending}
            </span>
            <span className="text-[11px] text-slate-400 font-medium">officer reviews</span>
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {overview.reviews.critical > 0 ? (
              <span className="text-amber-700 font-semibold">{overview.reviews.critical} high priority</span>
            ) : (
              <span>Queue manageable</span>
            )}
          </div>
        </Link>

        {/* Metric 5: Conflicts */}
        <Link
          href="/admin/conflicts"
          className="bg-white p-2.5 rounded-xl border border-slate-200 hover:border-slate-300 hover:shadow-xs transition group"
        >
          <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold">
            <span>Conflicts</span>
            <span className={`w-2 h-2 rounded-full ${overview.conflicts.critical_count > 0 ? 'bg-rose-500' : 'bg-slate-300'}`} />
          </div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <span className={`text-xl font-black ${overview.conflicts.critical_count > 0 ? 'text-rose-600' : 'text-slate-900'}`}>
              {overview.conflicts.total_unresolved}
            </span>
            <span className="text-[11px] text-slate-400 font-medium">unresolved</span>
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            {overview.conflicts.critical_count > 0 ? (
              <span className="text-rose-600 font-semibold">{overview.conflicts.critical_count} critical blocker</span>
            ) : (
              <span>No blocking conflicts</span>
            )}
          </div>
        </Link>
      </div>

      {/* 3-Column Zero-Scroll Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 flex-1 min-h-0">
        {/* Column 1: Pipeline Breakdown (Compact List) */}
        <div className="bg-white rounded-xl border border-slate-200 p-3 flex flex-col min-h-0 shadow-xs">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <span>⚡</span>
              <span>Pipeline Stages</span>
            </h2>
            <Link
              href="/admin/processing"
              className="text-[11px] font-semibold text-orange-600 hover:text-orange-700 transition"
            >
              Inspect Queue →
            </Link>
          </div>
          <div className="mt-2 space-y-1.5 overflow-y-auto pr-1 flex-1">
            {(overview.pipeline_stages || []).slice(0, 7).map((stage, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-150 text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-400 flex-shrink-0" />
                  <span className="font-semibold text-slate-800 truncate text-[11px]">
                    {stage.stage.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 text-[11px]">
                  {stage.waiting > 0 && (
                    <span className="px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 font-bold text-[10px]">
                      {stage.waiting} wait
                    </span>
                  )}
                  {stage.processing > 0 && (
                    <span className="px-1.5 py-0.2 rounded bg-sky-100 text-sky-800 font-bold text-[10px] animate-pulse">
                      {stage.processing} proc
                    </span>
                  )}
                  {stage.failed > 0 && (
                    <span className="px-1.5 py-0.2 rounded bg-rose-100 text-rose-800 font-bold text-[10px]">
                      {stage.failed} fail
                    </span>
                  )}
                  {stage.waiting === 0 && stage.processing === 0 && stage.failed === 0 && (
                    <span className="text-slate-400 text-[10px]">Idle</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Column 2: Critical Alerts & Subsystems */}
        <div className="bg-white rounded-xl border border-slate-200 p-3 flex flex-col min-h-0 shadow-xs">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <span>⚠️</span>
              <span>Priority Alerts & Health</span>
            </h2>
            <Link
              href="/admin/conflicts"
              className="text-[11px] font-semibold text-orange-600 hover:text-orange-700 transition"
            >
              All Alerts →
            </Link>
          </div>

          <div className="mt-2 space-y-2 overflow-y-auto pr-1 flex-1">
            {overview.critical_issues && overview.critical_issues.length > 0 ? (
              overview.critical_issues.slice(0, 4).map((issue) => (
                <div
                  key={issue.id}
                  className="p-2 rounded-lg bg-rose-50/70 border border-rose-200 text-xs flex flex-col gap-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-rose-900 text-[11px] truncate">{issue.title}</span>
                    <span className="text-[9px] uppercase font-black px-1.5 py-0.5 rounded bg-rose-200 text-rose-800">
                      {issue.severity}
                    </span>
                  </div>
                  <p className="text-[10px] text-rose-700 line-clamp-1">{issue.description}</p>
                </div>
              ))
            ) : (
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-center my-auto">
                <div className="text-emerald-700 font-bold text-xs">All Systems Nominal</div>
                <div className="text-[10px] text-emerald-600 mt-0.5">
                  No critical pipeline blockers or schema verification discrepancies detected.
                </div>
              </div>
            )}

            {/* Quick Subsystems Status Row */}
            <div className="mt-auto pt-2 border-t border-slate-100 grid grid-cols-3 gap-1.5 text-center text-[10px]">
              <div className="p-1 rounded bg-slate-50 border border-slate-200">
                <span className="font-bold text-slate-700">Database</span>
                <div className="text-emerald-600 font-bold mt-0.5">● Connected</div>
              </div>
              <div className="p-1 rounded bg-slate-50 border border-slate-200">
                <span className="font-bold text-slate-700">Vector Store</span>
                <div className="text-emerald-600 font-bold mt-0.5">● Synced</div>
              </div>
              <div className="p-1 rounded bg-slate-50 border border-slate-200">
                <span className="font-bold text-slate-700">OCR Engine</span>
                <div className="text-emerald-600 font-bold mt-0.5">● Online</div>
              </div>
            </div>
          </div>
        </div>

        {/* Column 3: Quick Shortcuts & Live Activity */}
        <div className="bg-white rounded-xl border border-slate-200 p-3 flex flex-col min-h-0 shadow-xs">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
              <span>📋</span>
              <span>Shortcuts & Activity</span>
            </h2>
            <Link
              href="/admin/activity"
              className="text-[11px] font-semibold text-orange-600 hover:text-orange-700 transition"
            >
              Full Log →
            </Link>
          </div>

          {/* Quick Action Buttons */}
          <div className="grid grid-cols-2 gap-1.5 my-2">
            <Link
              href="/admin/review"
              className="p-1.5 rounded-lg border border-slate-200 hover:border-orange-300 hover:bg-orange-50 text-left transition flex items-center justify-between"
            >
              <div>
                <div className="text-[11px] font-bold text-slate-800">Verification</div>
                <div className="text-[9px] text-slate-500">Day 13 Officer Review</div>
              </div>
              <span className="text-xs text-orange-600">→</span>
            </Link>
            <Link
              href="/admin/processing"
              className="p-1.5 rounded-lg border border-slate-200 hover:border-orange-300 hover:bg-orange-50 text-left transition flex items-center justify-between"
            >
              <div>
                <div className="text-[11px] font-bold text-slate-800">Pipeline Queue</div>
                <div className="text-[9px] text-slate-500">Queue & Retries</div>
              </div>
              <span className="text-xs text-orange-600">→</span>
            </Link>
          </div>

          {/* Activity Stream */}
          <div className="space-y-1.5 overflow-y-auto pr-1 flex-1">
            {activities.slice(0, 4).map((act, i) => (
              <div
                key={act.id || i}
                className="p-1.5 rounded-md bg-slate-50 border border-slate-150 text-[11px] flex items-center justify-between"
              >
                <div className="truncate pr-2">
                  <span className="font-semibold text-slate-800 mr-1.5">{act.title}</span>
                  <span className="text-[10px] text-slate-500 truncate">{act.description}</span>
                </div>
                <span className="text-[9px] text-slate-400 font-mono whitespace-nowrap">
                  {act.timestamp ? new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
