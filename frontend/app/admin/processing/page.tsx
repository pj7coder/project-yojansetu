"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getAdminPipeline, retryAdminDocument } from "../../../lib/api";
import { AdminPipelineResponse, StuckItem, PipelineStageCount } from "../../../types/admin";
import { StatusBadge } from "../../../components/admin/StatusBadge";
import { DataTable } from "../../../components/admin/DataTable";

export default function AdminProcessingPage() {
  const [pipeline, setPipeline] = useState<AdminPipelineResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const loadPipeline = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminPipeline();
      setPipeline(res);
    } catch (err: any) {
      console.error("Failed to load pipeline queue data:", err);
      setError(err.message || "Failed to load pipeline workload.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPipeline();
  }, [loadPipeline]);

  const handleRetry = async (item: StuckItem) => {
    if (!item.valid_retry_action) return;
    setRetryingId(item.document_id);
    setActionNotice(null);
    try {
      const res = await retryAdminDocument(item.document_id, item.valid_retry_action);
      setActionNotice(`Document ${item.document_code}: ${res.message}`);
      await loadPipeline();
    } catch (err: any) {
      setError(err.message || "Retry action failed.");
    } finally {
      setRetryingId(null);
    }
  };

  const formatWaitTime = (seconds?: number | null) => {
    if (!seconds || seconds <= 0) return "—";
    const mins = Math.floor(seconds / 60);
    const hrs = Math.floor(mins / 60);
    if (hrs > 0) return `${hrs}h ${mins % 60}m`;
    if (mins > 0) return `${mins}m`;
    return `${seconds}s`;
  };

  const stageColumns = [
    {
      header: "Pipeline Stage",
      render: (s: PipelineStageCount) => (
        <span className="font-bold text-slate-900">{s.stage}</span>
      ),
    },
    {
      header: "Waiting",
      render: (s: PipelineStageCount) => (
        <span
          className={`font-mono font-semibold ${
            s.waiting > 0 ? "text-amber-700" : "text-slate-500"
          }`}
        >
          {s.waiting}
        </span>
      ),
    },
    {
      header: "Processing",
      render: (s: PipelineStageCount) => (
        <span
          className={`font-mono font-semibold ${
            s.processing > 0 ? "text-blue-700" : "text-slate-500"
          }`}
        >
          {s.processing}
        </span>
      ),
    },
    {
      header: "Failed",
      render: (s: PipelineStageCount) => (
        <span
          className={`font-mono font-semibold ${
            s.failed > 0 ? "text-rose-700" : "text-slate-500"
          }`}
        >
          {s.failed}
        </span>
      ),
    },
    {
      header: "Oldest Waiting",
      render: (s: PipelineStageCount) => (
        <span className="text-[11px] font-mono text-slate-600">
          {formatWaitTime(s.oldest_waiting_seconds)}
        </span>
      ),
    },
    {
      header: "State",
      render: (s: PipelineStageCount) => {
        const state = s.failed > 0 ? "FAILED" : s.processing > 0 ? "BUSY" : s.waiting > 0 ? "WAITING" : "IDLE";
        return <StatusBadge status={state} />;
      },
    },
  ];

  const stuckColumns = [
    {
      header: "Document Code",
      render: (item: StuckItem) => (
        <div className="space-y-0.5">
          <span className="font-bold text-slate-900">{item.document_code}</span>
          {item.title && <div className="text-[11px] text-slate-500">{item.title}</div>}
        </div>
      ),
    },
    {
      header: "Stage",
      render: (item: StuckItem) => (
        <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200">
          {item.stage}
        </span>
      ),
    },
    {
      header: "Current Status",
      render: (item: StuckItem) => <StatusBadge status={item.status} />,
    },
    {
      header: "Stuck Duration",
      render: (item: StuckItem) => (
        <span className="font-mono text-xs font-semibold text-rose-700">
          {item.elapsed_minutes} minutes
        </span>
      ),
    },
    {
      header: "Safe Recovery",
      render: (item: StuckItem) => {
        if (!item.retry_valid || !item.valid_retry_action) {
          return <span className="text-slate-400 text-[11px]">Manual check required</span>;
        }

        const isRetrying = retryingId === item.document_id;
        const label = item.valid_retry_action.replace(/_/g, " ").toLowerCase();

        return (
          <button
            onClick={() => handleRetry(item)}
            disabled={isRetrying}
            className="text-[11px] font-semibold text-rose-700 hover:text-rose-900 border border-rose-200 hover:border-rose-300 rounded px-2.5 py-1 bg-rose-50 hover:bg-rose-100 transition capitalize disabled:opacity-50"
          >
            {isRetrying ? "Retrying..." : label}
          </button>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Pipeline Workload & Queue Operations
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Stage queue depths, oldest waiting thresholds, and deterministic stuck-item detection
          </p>
        </div>
        <button
          onClick={() => loadPipeline()}
          className="text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1.5 rounded bg-white border border-slate-300 hover:bg-slate-50 transition"
        >
          Refresh Queue
        </button>
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

      {/* Summary Totals */}
      {pipeline && (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm text-center">
            <div className="text-xs uppercase text-slate-500 font-semibold tracking-wider">
              Total Waiting
            </div>
            <div className="text-2xl font-bold text-amber-700 mt-1 font-mono">
              {pipeline.total_waiting}
            </div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm text-center">
            <div className="text-xs uppercase text-slate-500 font-semibold tracking-wider">
              Actively Processing
            </div>
            <div className="text-2xl font-bold text-blue-700 mt-1 font-mono">
              {pipeline.total_processing}
            </div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm text-center">
            <div className="text-xs uppercase text-slate-500 font-semibold tracking-wider">
              Total Failed
            </div>
            <div className="text-2xl font-bold text-rose-700 mt-1 font-mono">
              {pipeline.total_failed}
            </div>
          </div>
        </div>
      )}

      {/* Stuck Processing Detection Alert */}
      {pipeline && pipeline.stuck_items.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-base">⚠️</span>
              <h2 className="text-sm font-bold text-slate-900">
                Stuck Processing Items ({pipeline.stuck_items.length})
              </h2>
            </div>
            <span className="text-[11px] text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 font-medium">
              Elapsed &gt; 30 Minutes Without Progress
            </span>
          </div>
          <DataTable
            columns={stuckColumns}
            data={pipeline.stuck_items}
            isLoading={isLoading}
            emptyMessage="No stuck pipeline items detected."
          />
        </div>
      )}

      {/* 10-Stage Queue Breakdown Table */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold text-slate-900">
          Queue Depth by Processing Stage
        </h2>
        <DataTable
          columns={stageColumns}
          data={pipeline?.stages || []}
          isLoading={isLoading}
          emptyMessage="No pipeline stages registered."
        />
      </div>
    </div>
  );
}
