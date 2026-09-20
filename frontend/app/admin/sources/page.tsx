"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getAdminSources, triggerManualSourceCheck } from "../../../lib/api";
import { AdminSourceListItem } from "../../../types/admin";
import { StatusBadge } from "../../../components/admin/StatusBadge";
import { DataTable } from "../../../components/admin/DataTable";

export default function AdminSourcesPage() {
  const [sources, setSources] = useState<AdminSourceListItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(20);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [priorityFilter, setPriorityFilter] = useState<string>("");
  const [authorityFilter, setAuthorityFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [enabledOnly, setEnabledOnly] = useState<boolean>(false);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [checkingId, setCheckingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const loadSources = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminSources({
        status: statusFilter || undefined,
        priority_tier: priorityFilter || undefined,
        authority_level: authorityFilter || undefined,
        enabled_only: enabledOnly ? true : undefined,
        query: searchQuery.trim() || undefined,
        page,
        page_size: pageSize,
      });
      setSources(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load sources:", err);
      setError(err.message || "Failed to load monitored sources.");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, priorityFilter, authorityFilter, enabledOnly, searchQuery, page, pageSize]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  const handleManualCheck = async (sourceUrlId?: string | null) => {
    if (!sourceUrlId) return;
    setCheckingId(sourceUrlId);
    setActionNotice(null);
    try {
      await triggerManualSourceCheck(sourceUrlId);
      setActionNotice(`Manual check triggered successfully for URL ID: ${sourceUrlId}`);
      await loadSources();
    } catch (err: any) {
      setError(err.message || "Failed to trigger source check.");
    } finally {
      setCheckingId(null);
    }
  };

  const columns = [
    {
      header: "Source & URL",
      render: (s: AdminSourceListItem) => (
        <div className="space-y-0.5">
          <div className="font-bold text-slate-900">{s.source_name}</div>
          <div className="text-[11px] text-slate-500 font-mono truncate max-w-xs" title={s.url}>
            {s.url}
          </div>
        </div>
      ),
    },
    {
      header: "Authority",
      render: (s: AdminSourceListItem) => (
        <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-700">
          {s.authority_level}
        </span>
      ),
    },
    {
      header: "Priority",
      render: (s: AdminSourceListItem) => (
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 font-semibold">
          {s.priority_tier}
        </span>
      ),
    },
    {
      header: "Monitor Status",
      render: (s: AdminSourceListItem) => <StatusBadge status={s.monitor_status} />,
    },
    {
      header: "Last Check",
      render: (s: AdminSourceListItem) => (
        <span className="text-[11px] text-slate-600 font-mono">
          {s.last_check_at ? new Date(s.last_check_at).toLocaleString() : "Never"}
        </span>
      ),
    },
    {
      header: "Failures",
      render: (s: AdminSourceListItem) => (
        <span
          className={`font-mono text-xs font-semibold ${
            s.failure_count > 0 ? "text-rose-600" : "text-slate-500"
          }`}
        >
          {s.failure_count}
        </span>
      ),
    },
    {
      header: "Actions",
      render: (s: AdminSourceListItem) => (
        <div className="flex items-center gap-2">
          {s.source_url_id && (
            <button
              onClick={() => handleManualCheck(s.source_url_id)}
              disabled={checkingId === s.source_url_id}
              className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 border border-blue-200 hover:border-blue-300 rounded px-2 py-0.5 bg-blue-50/50 hover:bg-blue-100/50 transition disabled:opacity-50"
            >
              {checkingId === s.source_url_id ? "Checking..." : "Check Now"}
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Government Source Registry & Monitors
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time monitoring health, check schedules, and content change detection
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadSources()}
            className="text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1 rounded bg-white border border-slate-300 hover:bg-slate-50 transition"
          >
            Refresh
          </button>
        </div>
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

      {/* Filter Bar */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm flex flex-wrap items-center gap-3 text-xs">
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Search by source name or URL..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="w-full h-8 px-2.5 bg-slate-50 border border-slate-300 rounded text-xs placeholder-slate-400 focus:outline-none focus:border-blue-500"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="h-8 px-2 bg-slate-50 border border-slate-300 rounded text-xs"
        >
          <option value="">All Statuses</option>
          <option value="HEALTHY">Healthy</option>
          <option value="CHECK_FAILED">Check Failed</option>
          <option value="CHANGED">Changed</option>
          <option value="NEVER_CHECKED">Never Checked</option>
          <option value="DISABLED">Disabled</option>
        </select>

        <select
          value={priorityFilter}
          onChange={(e) => {
            setPriorityFilter(e.target.value);
            setPage(1);
          }}
          className="h-8 px-2 bg-slate-50 border border-slate-300 rounded text-xs"
        >
          <option value="">All Priorities</option>
          <option value="TIER_1">Tier 1 (High)</option>
          <option value="TIER_2">Tier 2 (Medium)</option>
          <option value="TIER_3">Tier 3 (Low)</option>
        </select>

        <select
          value={authorityFilter}
          onChange={(e) => {
            setAuthorityFilter(e.target.value);
            setPage(1);
          }}
          className="h-8 px-2 bg-slate-50 border border-slate-300 rounded text-xs"
        >
          <option value="">All Authorities</option>
          <option value="OFFICIAL_PORTAL">Official Portal</option>
          <option value="DEPARTMENT_PORTAL">Department Portal</option>
          <option value="GAZETTE">Gazette</option>
        </select>

        <label className="flex items-center gap-1.5 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={enabledOnly}
            onChange={(e) => {
              setEnabledOnly(e.target.checked);
              setPage(1);
            }}
            className="rounded text-blue-600 focus:ring-0"
          />
          <span className="text-slate-700">Enabled only</span>
        </label>
      </div>

      {/* Sources Data Table */}
      <DataTable
        columns={columns}
        data={sources}
        isLoading={isLoading}
        emptyMessage="No monitored sources match the specified criteria."
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}
