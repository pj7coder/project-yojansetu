"use client";

import React from "react";
import { Pagination } from "./Pagination";

interface Column<T> {
  header: string;
  accessor?: keyof T;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  isLoading?: boolean;
  emptyMessage?: string;
  page?: number;
  pageSize?: number;
  total?: number;
  onPageChange?: (newPage: number) => void;
  rowKey?: (item: T) => string;
}

export function DataTable<T>({
  columns,
  data,
  isLoading = false,
  emptyMessage = "No records found.",
  page,
  pageSize,
  total,
  onPageChange,
  rowKey,
}: DataTableProps<T>) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden flex flex-col">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
              {columns.map((col, idx) => (
                <th key={idx} className={`px-4 py-3 ${col.className || ""}`}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-800">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center text-slate-500">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <span className="animate-spin text-lg">⏳</span>
                    <span>Loading operational records...</span>
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center text-slate-500">
                  <div className="flex flex-col items-center justify-center gap-1.5">
                    <span className="text-base text-slate-400">∅</span>
                    <span>{emptyMessage}</span>
                  </div>
                </td>
              </tr>
            ) : (
              data.map((item, rowIdx) => {
                const key = rowKey ? rowKey(item) : (item as any).id || rowIdx;
                return (
                  <tr key={key} className="hover:bg-slate-50/80 transition-colors">
                    {columns.map((col, colIdx) => (
                      <td key={colIdx} className={`px-4 py-3 ${col.className || ""}`}>
                        {col.render
                          ? col.render(item)
                          : col.accessor
                          ? String(item[col.accessor] ?? "—")
                          : null}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {page && pageSize && total !== undefined && onPageChange && (
        <Pagination
          page={page}
          pageSize={pageSize}
          total={total}
          onPageChange={onPageChange}
        />
      )}
    </div>
  );
}
