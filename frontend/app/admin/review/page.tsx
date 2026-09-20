"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getReviewQueue } from "../../../lib/api";
import { ReviewQueueItem } from "../../../types/review";

export default function AdminReviewQueuePage() {
  const [items, setItems] = useState<ReviewQueueItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(25);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchQueue = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getReviewQueue(
        page,
        pageSize,
        statusFilter || undefined
      );
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      setError(err.message || "Failed to load review queue.");
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, statusFilter]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const filteredItems = items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      item.scheme_name.toLowerCase().includes(query) ||
      (item.department_name && item.department_name.toLowerCase().includes(query)) ||
      item.internal_scheme_code.toLowerCase().includes(query) ||
      item.source_filename.toLowerCase().includes(query)
    );
  });

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col">
      {/* Admin Top Navbar */}
      <header className="bg-slate-900 text-white border-b border-slate-800 px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="font-bold text-base tracking-tight text-white flex items-center gap-2">
            <span>🛡 JanSetu</span>
            <span className="text-[11px] font-semibold px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
              Admin Workspace
            </span>
          </Link>
          <span className="text-slate-600">/</span>
          <span className="text-sm text-slate-300 font-medium">Human Verification Queue</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="px-2 py-1 rounded bg-slate-800 text-slate-300 font-mono">
            Reviewer: DEV_REVIEWER
          </span>
          <Link
            href="/documents"
            className="text-slate-400 hover:text-white transition"
          >
            Documents
          </Link>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-5">
        {/* Title & Queue Stats Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Human Review Queue
            </h1>
            <p className="text-xs text-slate-500 mt-1">
              Prioritized government schemes awaiting human verification before publication.
            </p>
          </div>
          <button
            type="button"
            onClick={() => fetchQueue()}
            disabled={isLoading}
            className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 transition shadow-xs flex items-center gap-1 self-start sm:self-auto"
          >
            ↻ Refresh Queue
          </button>
        </div>

        {/* Filters and Search Bar */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-wrap flex-1">
            {/* Search */}
            <div className="relative min-w-[240px] flex-1 max-w-md">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search scheme name, code, department..."
                className="w-full text-xs pl-8 pr-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-slate-50/50"
              />
              <span className="absolute left-2.5 top-2.5 text-slate-400 text-xs">🔍</span>
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="text-xs p-2 rounded-lg border border-slate-300 bg-white"
            >
              <option value="">All Statuses</option>
              <option value="READY_FOR_HUMAN_REVIEW">READY_FOR_HUMAN_REVIEW</option>
              <option value="IN_HUMAN_REVIEW">IN_HUMAN_REVIEW</option>
              <option value="HUMAN_VERIFIED">HUMAN_VERIFIED</option>
              <option value="HUMAN_REJECTED">HUMAN_REJECTED</option>
            </select>
          </div>

          <div className="text-xs text-slate-500 font-medium">
            Total Schemes: <strong className="text-slate-800">{total}</strong>
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 flex items-center justify-between">
            <span>⚠ {error}</span>
            <button
              onClick={() => fetchQueue()}
              className="font-bold underline ml-3 text-red-900"
            >
              Retry
            </button>
          </div>
        )}

        {/* Queue Items Table / Cards */}
        {isLoading ? (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-xs text-slate-500 space-y-2">
            <div className="animate-spin text-2xl">⚙</div>
            <div>Loading prioritized review queue...</div>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl p-12 text-center text-slate-500 space-y-2">
            <div className="text-3xl">📭</div>
            <div className="text-sm font-semibold text-slate-800">
              No scheme drafts found
            </div>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              There are no scheme drafts matching the selected filters. Upload and process a
              government PDF to generate canonical drafts.
            </p>
          </div>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                    <th className="px-4 py-3">Scheme & Department</th>
                    <th className="px-3 py-3">Status</th>
                    <th className="px-3 py-3 text-center">Contradictions</th>
                    <th className="px-3 py-3 text-center">OCR Risk</th>
                    <th className="px-3 py-3 text-center">Conflicts</th>
                    <th className="px-3 py-3 text-center">Blockers/Errors</th>
                    <th className="px-3 py-3 text-center">Progress</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredItems.map((item) => (
                    <tr
                      key={item.draft_id}
                      className="hover:bg-slate-50/80 transition"
                    >
                      {/* Scheme & Department */}
                      <td className="px-4 py-3 max-w-xs sm:max-w-sm">
                        <div className="font-bold text-slate-900 line-clamp-1">
                          {item.scheme_name}
                        </div>
                        <div className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                          {item.department_name || "Department not specified"}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400 mt-1 flex items-center gap-2">
                          <span>{item.internal_scheme_code}</span>
                          <span>•</span>
                          <span>📄 {item.source_filename}</span>
                        </div>
                      </td>

                      {/* Status */}
                      <td className="px-3 py-3 whitespace-nowrap">
                        {item.draft_status === "HUMAN_VERIFIED" ? (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
                            ✓ VERIFIED
                          </span>
                        ) : item.draft_status === "HUMAN_REJECTED" ? (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-red-100 text-red-800 border border-red-300">
                            ✕ REJECTED
                          </span>
                        ) : item.draft_status === "IN_HUMAN_REVIEW" ? (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-100 text-blue-800 border border-blue-300">
                            ● IN REVIEW
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                            READY
                          </span>
                        )}
                      </td>

                      {/* Contradictions */}
                      <td className="px-3 py-3 text-center whitespace-nowrap">
                        {item.contradicted_facts > 0 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-red-100 text-red-800 border border-red-300">
                            {item.contradicted_facts} contradicted
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* OCR Risk */}
                      <td className="px-3 py-3 text-center whitespace-nowrap">
                        {item.ocr_risks > 0 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-orange-100 text-orange-900 border border-orange-300">
                            {item.ocr_risks} OCR risks
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Conflicts */}
                      <td className="px-3 py-3 text-center whitespace-nowrap">
                        {item.conflicts > 0 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-purple-100 text-purple-800 border border-purple-300">
                            {item.conflicts} conflicts
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Blockers / Errors */}
                      <td className="px-3 py-3 text-center whitespace-nowrap">
                        {item.critical_issues > 0 ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-rose-100 text-rose-900 border border-rose-300">
                            {item.critical_issues} issues
                          </span>
                        ) : (
                          <span className="text-slate-400">0</span>
                        )}
                      </td>

                      {/* Progress */}
                      <td className="px-3 py-3 text-center whitespace-nowrap font-mono text-[11px] text-slate-700">
                        {item.resolved_facts} / {item.total_facts}
                      </td>

                      {/* Action */}
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <Link
                          href={`/admin/review/${item.draft_id}`}
                          className="px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 transition shadow-xs"
                        >
                          Review Draft →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
