"use client";

import React from "react";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (newPage: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between px-4 py-3 bg-white border-t border-slate-200 text-xs text-slate-700">
      <div>
        Showing <span className="font-semibold">{Math.min((page - 1) * pageSize + 1, total)}</span> to{" "}
        <span className="font-semibold">{Math.min(page * pageSize, total)}</span> of{" "}
        <span className="font-semibold">{total}</span> items
      </div>

      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="px-2.5 py-1 rounded border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium transition"
        >
          ← Previous
        </button>

        <span className="px-2 font-mono text-slate-500">
          Page {page} of {totalPages}
        </span>

        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="px-2.5 py-1 rounded border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium transition"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
