"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  getAdminSystemStatus,
  refreshRuleCache,
  reindexStaleEmbeddings,
  resetAllPlatformData,
} from "../../../lib/api";
import { AdminSystemStatusResponse } from "../../../types/admin";
import { StatusBadge } from "../../../components/admin/StatusBadge";
import { DataTable } from "../../../components/admin/DataTable";

export default function AdminSystemPage() {
  const [status, setStatus] = useState<AdminSystemStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [isRefreshingCache, setIsRefreshingCache] = useState<boolean>(false);
  const [isReindexing, setIsReindexing] = useState<boolean>(false);

  // System Factory Reset Modal State
  const [showResetModal, setShowResetModal] = useState<boolean>(false);
  const [resetConfirmation, setResetConfirmation] = useState<string>("");
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [resetModalError, setResetModalError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminSystemStatus();
      setStatus(res);
    } catch (err: any) {
      console.error("Failed to load system status:", err);
      setError(err.message || "Failed to load system status.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleRefreshCache = async () => {
    setIsRefreshingCache(true);
    setActionNotice(null);
    try {
      const res = await refreshRuleCache();
      setActionNotice(res.message);
      await loadStatus();
    } catch (err: any) {
      setError(err.message || "Failed to refresh rule cache.");
    } finally {
      setIsRefreshingCache(false);
    }
  };

  const handleReindex = async () => {
    setIsReindexing(true);
    setActionNotice(null);
    try {
      const res = await reindexStaleEmbeddings();
      setActionNotice(res.message);
      await loadStatus();
    } catch (err: any) {
      setError(err.message || "Failed to rebuild embeddings.");
    } finally {
      setIsReindexing(false);
    }
  };

  const handleResetPlatform = async () => {
    if (resetConfirmation.trim() !== "DELETE") {
      setResetModalError("You must type DELETE in all caps to confirm.");
      return;
    }
    setIsResetting(true);
    setResetModalError(null);
    try {
      const res = await resetAllPlatformData(resetConfirmation.trim());
      setShowResetModal(false);
      setResetConfirmation("");
      setActionNotice(res.message || "All platform data has been reset to a clean state.");
      await loadStatus();
    } catch (err: any) {
      setResetModalError(err.message || "Failed to reset platform data.");
    } finally {
      setIsResetting(false);
    }
  };

  const workerColumns = [
    {
      header: "Worker Type",
      accessor: "worker_type" as const,
      render: (w: any) => <span className="font-bold text-slate-900">{w.worker_type}</span>,
    },
    {
      header: "Instance ID",
      accessor: "worker_instance_id" as const,
      render: (w: any) => <span className="font-mono text-slate-600">{w.worker_instance_id}</span>,
    },
    {
      header: "Heartbeat State",
      render: (w: any) => (
        <StatusBadge status={w.is_stale ? "STALE" : w.status} />
      ),
    },
    {
      header: "Last Seen",
      render: (w: any) => (
        <span className="text-[11px] font-mono text-slate-600">
          {new Date(w.last_seen_at).toLocaleTimeString()} ({new Date(w.last_seen_at).toLocaleDateString()})
        </span>
      ),
    },
  ];

  if (isLoading && !status) {
    return (
      <div className="py-20 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
        <span className="text-xl animate-spin">⏳</span>
        <span>Probing backend subsystem health...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-slate-200">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            System Operations & Subsystem Health
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Operational status of PostgreSQL, Ollama extraction daemon, pgvector search index, and verified rule cache
          </p>
        </div>
        <button
          onClick={() => loadStatus()}
          className="text-xs text-slate-600 hover:text-slate-900 px-2.5 py-1.5 rounded bg-white border border-slate-300 hover:bg-slate-50 transition"
        >
          Re-Probe Health
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

      {status && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* 1. Database Health */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">🗄️</span>
                <h2 className="text-sm font-bold text-slate-900">PostgreSQL Database</h2>
              </div>
              <StatusBadge status={status.database.status} />
            </div>
            <div className="grid grid-cols-3 gap-2 pt-2 border-t text-xs">
              <div>
                <div className="text-slate-500 text-[11px]">Pool Size</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">{status.database.pool_size}</div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">Overflow</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">{status.database.overflow}</div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">Probe Latency</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">
                  {status.database.latency_ms !== null ? `${status.database.latency_ms} ms` : "—"}
                </div>
              </div>
            </div>
          </div>

          {/* 2. Ollama Health */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">🦙</span>
                <h2 className="text-sm font-bold text-slate-900">Ollama LLM Server</h2>
              </div>
              <StatusBadge status={status.ollama.status} />
            </div>
            <div className="grid grid-cols-3 gap-2 pt-2 border-t text-xs">
              <div>
                <div className="text-slate-500 text-[11px]">Configured Model</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">{status.ollama.model}</div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">Provider</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">{status.ollama.provider}</div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">Model Loaded</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">
                  {status.ollama.model_available ? "Yes (Active)" : "Offline / Unpulled"}
                </div>
              </div>
            </div>
          </div>

          {/* 3. pgvector & Search Index */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">🔎</span>
                <h2 className="text-sm font-bold text-slate-900">pgvector & Semantic Index</h2>
              </div>
              <StatusBadge status={status.search_index.status} />
            </div>
            <div className="grid grid-cols-3 gap-2 pt-2 border-t text-xs">
              <div>
                <div className="text-slate-500 text-[11px]">Indexed Schemes</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">{status.search_index.embeddings_count}</div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">Stale Embeddings</div>
                <div className={`font-mono font-bold mt-0.5 ${status.search_index.stale_embeddings_count > 0 ? "text-amber-700" : "text-slate-800"}`}>
                  {status.search_index.stale_embeddings_count}
                </div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">pgvector Ext</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">
                  {status.search_index.pgvector_available ? "Available" : "Fallback (Text)"}
                </div>
              </div>
            </div>
            <div className="pt-2 flex items-center justify-between">
              <span className="text-[11px] text-slate-500 font-mono">
                Model: {status.search_index.embedding_model}
              </span>
              <button
                onClick={handleReindex}
                disabled={isReindexing}
                className="text-xs font-semibold text-blue-700 hover:text-blue-900 border border-blue-200 rounded px-2.5 py-1 bg-blue-50/60 hover:bg-blue-100 transition disabled:opacity-50"
              >
                {isReindexing ? "Re-indexing..." : "Rebuild Embeddings"}
              </button>
            </div>
          </div>

          {/* 4. Verified Rule Cache */}
          <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-lg">⚡</span>
                <h2 className="text-sm font-bold text-slate-900">Verified Rule Cache</h2>
              </div>
              <StatusBadge status={status.rule_cache.status} />
            </div>
            <div className="grid grid-cols-4 gap-2 pt-2 border-t text-xs">
              <div>
                <div className="text-slate-500 text-[11px]">Cached Entries</div>
                <div className="font-mono font-bold text-slate-800 mt-0.5">{status.rule_cache.entries}</div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">Cache Hits</div>
                <div className="font-mono font-bold text-emerald-700 mt-0.5">{status.rule_cache.hits}</div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">Cache Misses</div>
                <div className="font-mono font-bold text-slate-700 mt-0.5">{status.rule_cache.misses}</div>
              </div>
              <div>
                <div className="text-slate-500 text-[11px]">Refreshes</div>
                <div className="font-mono font-bold text-blue-700 mt-0.5">{status.rule_cache.refreshes}</div>
              </div>
            </div>
            <div className="pt-2 flex items-center justify-between">
              <span className="text-[11px] text-slate-500">
                In-memory compiled rule AST cache for citizen evaluation
              </span>
              <button
                onClick={handleRefreshCache}
                disabled={isRefreshingCache}
                className="text-xs font-semibold text-blue-700 hover:text-blue-900 border border-blue-200 rounded px-2.5 py-1 bg-blue-50/60 hover:bg-blue-100 transition disabled:opacity-50"
              >
                {isRefreshingCache ? "Refreshing..." : "Refresh Cache"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Storage Artifact Counts */}
      {status && (
        <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between pb-2 border-b">
            <h2 className="text-sm font-bold text-slate-900">Storage & Artifact Inventory</h2>
            <span className="text-[11px] text-slate-500">PostgreSQL Indexed Artifacts</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 text-center text-xs">
            <div className="p-2 rounded bg-slate-50 border border-slate-100">
              <div className="text-slate-500 text-[11px]">Documents</div>
              <div className="text-base font-bold text-slate-900 mt-1 font-mono">
                {status.storage.original_documents}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-50 border border-slate-100">
              <div className="text-slate-500 text-[11px]">Parsed</div>
              <div className="text-base font-bold text-slate-900 mt-1 font-mono">
                {status.storage.parsed_documents}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-50 border border-slate-100">
              <div className="text-slate-500 text-[11px]">OCR Runs</div>
              <div className="text-base font-bold text-slate-900 mt-1 font-mono">
                {status.storage.ocr_runs}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-50 border border-slate-100">
              <div className="text-slate-500 text-[11px]">Chunks</div>
              <div className="text-base font-bold text-slate-900 mt-1 font-mono">
                {status.storage.document_chunks}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-50 border border-slate-100">
              <div className="text-slate-500 text-[11px]">Scheme Drafts</div>
              <div className="text-base font-bold text-slate-900 mt-1 font-mono">
                {status.storage.scheme_drafts}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-50 border border-slate-100">
              <div className="text-slate-500 text-[11px]">Snapshots</div>
              <div className="text-base font-bold text-slate-900 mt-1 font-mono">
                {status.storage.source_snapshots}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-50 border border-slate-100">
              <div className="text-slate-500 text-[11px]">Verified Artifacts</div>
              <div className="text-base font-bold text-emerald-700 mt-1 font-mono">
                {status.storage.verified_scheme_artifacts}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Worker Heartbeats Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">Background Worker Liveness</h2>
          <span className="text-[11px] text-slate-500">
            Upsert heartbeats with 60s freshness window
          </span>
        </div>
        <DataTable
          columns={workerColumns}
          data={status?.workers || []}
          isLoading={isLoading}
          emptyMessage="No background workers currently registered."
        />
      </div>

      {/* Danger Zone: Factory Reset */}
      <div className="bg-rose-50/50 rounded-lg border-2 border-rose-200 p-5 shadow-sm space-y-3 mt-6">
        <div className="flex items-center justify-between pb-2 border-b border-rose-200">
          <div className="flex items-center gap-2">
            <span className="text-rose-600 text-base">⚠️</span>
            <h2 className="text-sm font-bold text-rose-900">Danger Zone: Complete Platform Reset</h2>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-rose-700 bg-rose-100 px-2.5 py-0.5 rounded border border-rose-200">
            Destructive Purge
          </span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-1">
          <div className="text-xs text-rose-800 space-y-1">
            <p className="font-semibold text-rose-900">
              Permanently wipe all previous schemes, circular documents, sources, review records, and pipeline storage.
            </p>
            <p className="text-[11px] text-rose-700">
              Pre-downloaded AI model weights, database schemas, and migration states are safely preserved.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setResetConfirmation("");
              setResetModalError(null);
              setShowResetModal(true);
            }}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 active:bg-rose-800 rounded-md shadow-sm hover:shadow transition whitespace-nowrap cursor-pointer"
          >
            <span>🗑️</span>
            <span>Reset All Data</span>
          </button>
        </div>
      </div>

      {/* Reset Confirmation Modal */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/70 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-2xl border border-rose-200 max-w-md w-full p-6 space-y-4 text-slate-900">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center text-lg shrink-0">
                ⚠️
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Confirm Platform Factory Reset
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  This destructive operation cannot be undone.
                </p>
              </div>
            </div>

            <div className="bg-rose-50 border border-rose-200 rounded-lg p-3 text-xs text-rose-800 space-y-1.5">
              <div className="font-semibold">The following will be completely deleted:</div>
              <ul className="list-disc pl-4 space-y-0.5 text-[11px] text-rose-700">
                <li>All verified schemes, versions, and drafts</li>
                <li>All uploaded circular PDFs and parsed chunks</li>
                <li>All monitored sources, check events, and change logs</li>
                <li>All validation issues, conflict records, and review audits</li>
                <li>All generated files in storage (audio, parsed, OCR, extracted)</li>
              </ul>
            </div>

            {resetModalError && (
              <div className="bg-rose-100 border border-rose-300 text-rose-800 text-xs rounded p-2.5 font-medium">
                {resetModalError}
              </div>
            )}

            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-700">
                To confirm, type <span className="font-mono text-rose-600 font-bold bg-rose-50 px-1 py-0.5 rounded border border-rose-200 select-all">DELETE</span> in all caps:
              </label>
              <input
                type="text"
                value={resetConfirmation}
                onChange={(e) => {
                  setResetConfirmation(e.target.value);
                  setResetModalError(null);
                }}
                placeholder="Type DELETE to enable reset"
                autoFocus
                disabled={isResetting}
                className="w-full px-3 py-2 text-xs font-mono rounded border border-slate-300 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:border-rose-500 bg-slate-50 uppercase placeholder:normal-case"
              />
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => {
                  if (!isResetting) {
                    setShowResetModal(false);
                    setResetConfirmation("");
                  }
                }}
                disabled={isResetting}
                className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-md transition disabled:opacity-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleResetPlatform}
                disabled={resetConfirmation.trim() !== "DELETE" || isResetting}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-md shadow-sm transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              >
                {isResetting && <span className="animate-spin">⏳</span>}
                <span>{isResetting ? "Resetting Everything..." : "Delete All Data"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
