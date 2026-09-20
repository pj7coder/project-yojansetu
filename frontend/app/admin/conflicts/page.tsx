"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getAdminConflicts } from "../../../lib/api";
import { AdminConflictItem } from "../../../types/admin";
import { StatusBadge } from "../../../components/admin/StatusBadge";
import { DataTable } from "../../../components/admin/DataTable";

export default function AdminConflictsPage() {
  const [conflicts, setConflicts] = useState<AdminConflictItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(20);

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [severityFilter, setSeverityFilter] = useState<string>("");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadConflicts = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminConflicts({
        conflict_type: typeFilter || undefined,
        severity: severityFilter || undefined,
        page,
        page_size: pageSize,
      });
      setConflicts(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load conflicts:", err);
      setError(err.message || "Failed to load system conflicts.");
    } finally {
      setIsLoading(false);
    }
  }, [typeFilter, severityFilter, page, pageSize]);

  useEffect(() => {
    loadConflicts();
  }, [loadConflicts]);

  const columns = [
    {
      header: "Conflict Description & Target",
      render: (c: AdminConflictItem) => (
        <div className="space-y-1">
          <div className="font-bold text-slate-900">{c.title}</div>
          <p className="text-xs text-slate-600 max-w-xl">{c.description}</p>
          {c.scheme_name && (
            <div className="text-[10px] text-slate-500">
              Scheme: <span className="font-medium text-slate-700">{c.scheme_name}</span>
            </div>
          )}
        </div>
      ),
    },
    {
      header: "Conflict Category",
      render: (c: AdminConflictItem) => (
        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold">
          {c.conflict_type}
        </span>
      ),
    },
    {
      header: "Severity",
      render: (c: AdminConflictItem) => <StatusBadge status={c.severity} size="sm" />,
    },
    {
      header: "Status",
      render: (c: AdminConflictItem) => (
        <span className="text-[10px] font-mono text-slate-600 px-2 py-0.5 rounded bg-slate-50 border border-slate-200">
          {c.status}
        </span>
      ),
    },
    {
      header: "Discovered",
      render: (c: AdminConflictItem) => (
        <span className="text-[11px] text-slate-500 font-mono">
          {new Date(c.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
        </span>
      ),
    },
    {
      header: "Resolution",
      render: (c: AdminConflictItem) => (
        <Link
          href={c.link}
          className="text-xs font-semibold text-blue-600 hover:text-blue-800 underline flex items-center gap-1"
        >
          <span>Open Review</span>
          <span>→</span>
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            System Operations Conflict Center
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Aggregated operational discrepancies across evidence contradictions, validation failures, and version change sets
          </p>
        </div>
        <button
          onClick={() => loadConflicts()}
          className="text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1.5 rounded bg-white border border-slate-300 hover:bg-slate-50 transition"
        >
          Refresh Conflicts
        </button>
      </div>

      {error && (
        <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-800 rounded">
          {error}
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm flex flex-wrap items-center gap-3 text-xs">
        <select
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value);
            setPage(1);
          }}
          className="h-8 px-2 bg-slate-50 border border-slate-300 rounded text-xs"
        >
          <option value="">All Conflict Types</option>
          <option value="FIELD_VALUE_CONFLICT">Evidence Contradiction (FIELD_VALUE_CONFLICT)</option>
          <option value="SCHEME_ASSOCIATION_CONFLICT">Validation Failure (SCHEME_ASSOCIATION_CONFLICT)</option>
          <option value="VERSION_RELATIONSHIP_CONFLICT">Version Change Conflict (VERSION_RELATIONSHIP_CONFLICT)</option>
          <option value="EFFECTIVE_DATE_CONFLICT">Effective Date Conflict (EFFECTIVE_DATE_CONFLICT)</option>
          <option value="SOURCE_CONFLICT">Source Discrepancy (SOURCE_CONFLICT)</option>
        </select>

        <select
          value={severityFilter}
          onChange={(e) => {
            setSeverityFilter(e.target.value);
            setPage(1);
          }}
          className="h-8 px-2 bg-slate-50 border border-slate-300 rounded text-xs"
        >
          <option value="">All Severities</option>
          <option value="CRITICAL">Critical Only</option>
          <option value="WARNING">Warning Only</option>
        </select>
      </div>

      {/* Conflicts Table */}
      <DataTable
        columns={columns}
        data={conflicts}
        isLoading={isLoading}
        emptyMessage="No unresolved conflicts recorded. All evidence assertions and version relationships are consistent."
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}
