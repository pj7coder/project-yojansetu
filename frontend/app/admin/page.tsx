"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getAdminOverview, getAdminActivity } from "../../lib/api";
import { AdminOverviewResponse, AdminActivityItem } from "../../types/admin";
import { MetricCard } from "../../components/admin/MetricCard";
import { PipelineStatus } from "../../components/admin/PipelineStatus";
import { CriticalIssues } from "../../components/admin/CriticalIssues";
import { RecentActivity } from "../../components/admin/RecentActivity";

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
        getAdminActivity(20),
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
      <div className="py-20 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
        <span className="text-xl animate-spin">⏳</span>
        <span>Aggregating operational metrics across subsystems...</span>
      </div>
    );
  }

  if (error && !overview) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-lg p-6 text-center text-xs">
        <div className="text-rose-800 font-semibold mb-2">Unable to load dashboard overview</div>
        <div className="text-rose-600 mb-4">{error}</div>
        <button
          onClick={loadData}
          className="px-3 py-1.5 rounded bg-rose-600 text-white font-medium hover:bg-rose-700 transition"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!overview) return null;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            System Operations Overview
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time observability and operational control across all JanSetu pipelines
          </p>
        </div>
        <div className="text-[11px] text-slate-400 font-mono">
          Updated: {new Date(overview.generated_at).toLocaleTimeString()}
        </div>
      </div>

      {/* Top-Level Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
        <MetricCard
          title="Active Sources"
          value={overview.sources.active}
          subtitle={`${overview.sources.total} total registered`}
          accent="emerald"
          link="/admin/sources"
        />
        <MetricCard
          title="Failing Sources"
          value={overview.sources.failing}
          subtitle="Check failures"
          accent={overview.sources.failing > 0 ? "rose" : "neutral"}
          link="/admin/sources?status=CHECK_FAILED"
          alertBadge={overview.sources.failing > 0 ? "ATTENTION" : undefined}
        />
        <MetricCard
          title="Documents Ingested"
          value={overview.documents.total}
          subtitle={`${overview.documents.processing} processing`}
          accent="sky"
          link="/admin/documents"
        />
        <MetricCard
          title="Failed Documents"
          value={overview.documents.failed}
          subtitle="Requires retry"
          accent={overview.documents.failed > 0 ? "rose" : "neutral"}
          link="/admin/documents?status=FAILED"
          alertBadge={overview.documents.failed > 0 ? "ACTION" : undefined}
        />
        <MetricCard
          title="Pending Reviews"
          value={overview.reviews.pending}
          subtitle={`${overview.reviews.critical} critical issues`}
          accent={overview.reviews.critical > 0 ? "amber" : "neutral"}
          link="/admin/review"
          alertBadge={overview.reviews.critical > 0 ? "URGENT" : undefined}
        />
        <MetricCard
          title="Verified Schemes"
          value={overview.schemes.human_verified}
          subtitle={`${overview.schemes.active_versions} active versions`}
          accent="emerald"
          link="/admin/schemes"
        />
        <MetricCard
          title="Future Versions"
          value={overview.schemes.future_versions}
          subtitle="Scheduled amendments"
          accent="sky"
          link="/admin/versions"
        />
        <MetricCard
          title="Recent Changes"
          value={overview.sources.recently_changed}
          subtitle="Last 24 hours"
          accent="amber"
          link="/admin/sources"
        />
        <MetricCard
          title="System Conflicts"
          value={overview.conflicts.total_unresolved}
          subtitle={`${overview.conflicts.critical_count} critical`}
          accent={overview.conflicts.critical_count > 0 ? "rose" : "neutral"}
          link="/admin/conflicts"
          alertBadge={overview.conflicts.critical_count > 0 ? "BLOCKER" : undefined}
        />
        <MetricCard
          title="Subsystem State"
          value={overview.system_status}
          subtitle={
            overview.system_status === "HEALTHY"
              ? "All nominal"
              : `${overview.system_status_reasons.length} warnings`
          }
          accent={
            overview.system_status === "HEALTHY"
              ? "emerald"
              : overview.system_status === "WARNING"
              ? "amber"
              : "rose"
          }
          link="/admin/system"
        />
      </div>

      {/* Critical Issues Banner */}
      <CriticalIssues issues={overview.critical_issues} />

      {/* Pipeline Workload Breakdown */}
      <PipelineStatus stages={overview.pipeline_stages} />

      {/* Two-Column Grid: Review Priority & Operational Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Recent Activity */}
        <div className="lg:col-span-2">
          <RecentActivity items={activities} />
        </div>

        {/* Right 1 Col: Quick Operational Links */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
              Operations Shortcuts
            </h3>
            <div className="space-y-2 text-xs">
              <Link
                href="/admin/processing"
                className="flex items-center justify-between p-2 rounded border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition"
              >
                <div>
                  <div className="font-semibold text-slate-800">Pipeline Workload</div>
                  <div className="text-[11px] text-slate-500">Stuck item inspection & queue depths</div>
                </div>
                <span className="text-slate-400">→</span>
              </Link>
              <Link
                href="/admin/review"
                className="flex items-center justify-between p-2 rounded border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition"
              >
                <div>
                  <div className="font-semibold text-slate-800">Human Verification Queue</div>
                  <div className="text-[11px] text-slate-500">Day 13 officer review & claim approval</div>
                </div>
                <span className="text-slate-400">→</span>
              </Link>
              <Link
                href="/admin/system"
                className="flex items-center justify-between p-2 rounded border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition"
              >
                <div>
                  <div className="font-semibold text-slate-800">System Control Center</div>
                  <div className="text-[11px] text-slate-500">DB, Ollama, pgvector & rule cache</div>
                </div>
                <span className="text-slate-400">→</span>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
