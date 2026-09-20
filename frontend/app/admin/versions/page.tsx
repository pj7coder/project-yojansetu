"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getAdminSchemes } from "../../../lib/api";
import { AdminSchemeListItem } from "../../../types/admin";
import { StatusBadge } from "../../../components/admin/StatusBadge";
import { DataTable } from "../../../components/admin/DataTable";

export default function AdminVersionsPage() {
  const [schemes, setSchemes] = useState<AdminSchemeListItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(25);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadVersions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminSchemes({
        page,
        page_size: pageSize,
      });
      setSchemes(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load scheme versions:", err);
      setError(err.message || "Failed to load version history.");
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    loadVersions();
  }, [loadVersions]);

  const columns = [
    {
      header: "Scheme Code & Title",
      render: (s: AdminSchemeListItem) => (
        <div className="space-y-0.5">
          <div className="font-bold text-slate-900">{s.name_en}</div>
          <div className="text-[10px] font-mono text-slate-500">{s.scheme_code}</div>
        </div>
      ),
    },
    {
      header: "Active Version",
      render: (s: AdminSchemeListItem) => (
        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-xs text-blue-700">
            {s.current_version_number ? `v${s.current_version_number}` : "—"}
          </span>
          {s.current_version_status && (
            <StatusBadge status={s.current_version_status} size="sm" />
          )}
        </div>
      ),
    },
    {
      header: "Amendment State",
      render: (s: AdminSchemeListItem) => {
        if (s.has_future_version) {
          return (
            <div className="space-y-0.5">
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                Future-Effective Version
              </span>
              <div className="text-[10px] text-slate-600 font-mono">
                Effective: {s.future_effective_date || "Pending Review"}
              </div>
            </div>
          );
        }
        return (
          <span className="text-[11px] text-slate-500">
            Current version is active policy
          </span>
        );
      },
    },
    {
      header: "Evaluation Status",
      render: (s: AdminSchemeListItem) => (
        <StatusBadge status={s.is_active ? "ACTIVE" : "INACTIVE"} />
      ),
    },
    {
      header: "Timeline Link",
      render: (s: AdminSchemeListItem) => (
        <Link
          href={`/admin/schemes?query=${encodeURIComponent(s.scheme_code)}`}
          className="text-xs font-semibold text-blue-600 hover:text-blue-800 underline"
        >
          View Scheme Corpus →
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Scheme Versioning & Amendment Timeline
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Observability over active versions, superseded historical versions, and future-effective amendments
          </p>
        </div>
        <button
          onClick={() => loadVersions()}
          className="text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1.5 rounded bg-white border border-slate-300 hover:bg-slate-50 transition"
        >
          Refresh Versions
        </button>
      </div>

      {error && (
        <div className="p-3 text-xs bg-rose-50 border border-rose-200 text-rose-800 rounded">
          {error}
        </div>
      )}

      {/* Conceptual Explanation Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-900 space-y-1">
        <div className="font-bold flex items-center gap-1.5">
          <span>ℹ️</span>
          <span>Day 19 Immutable Scheme Version Architecture</span>
        </div>
        <p className="text-blue-800 leading-relaxed">
          JanSetu maintains strict version immutability. When government circulars amend eligibility criteria or benefits,
          new versions are drafted and verified without overwriting previous versions. Amendments with future legal effective
          dates are labeled as <span className="font-semibold">Future-Effective</span> and remain inactive until their legal start date.
        </p>
      </div>

      {/* Versions Table */}
      <DataTable
        columns={columns}
        data={schemes}
        isLoading={isLoading}
        emptyMessage="No scheme versions found."
        page={page}
        pageSize={pageSize}
        total={total}
        onPageChange={(p) => setPage(p)}
      />
    </div>
  );
}
