"use client";

import React from "react";
import { HealthState } from "../../types/health";
import { config } from "../../lib/config";

interface StatusCardProps {
  state: HealthState;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export function StatusCard({ state, onRefresh, isRefreshing }: StatusCardProps) {
  const isBackendConnected = state.status === "connected";
  const isBackendChecking = state.status === "checking";
  const isBackendUnavailable = state.status === "unavailable";

  const isDbConnected = state.databaseStatus === "connected";
  const isDbChecking = state.databaseStatus === "checking";
  const isDbUnavailable = state.databaseStatus === "unavailable";

  return (
    <div
      role="region"
      aria-label="System Connection Status"
      className="w-full max-w-2xl bg-white border border-slate-200 rounded-2xl shadow-sm p-6 sm:p-8 transition-all"
    >
      {/* Header section with status badges */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            System Status
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
              Day 2 Foundation
            </span>
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Real-time backend and database communication test
          </p>
        </div>

        {/* Dynamic Status Badges */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Backend Status */}
          {isBackendChecking && (
            <span
              id="status-badge"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
              </span>
              Backend: Checking...
            </span>
          )}

          {isBackendConnected && (
            <span
              id="status-badge"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200"
            >
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
              Backend: Connected ✓
            </span>
          )}

          {isBackendUnavailable && (
            <span
              id="status-badge"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200"
            >
              <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-600"></span>
              Backend: Unavailable ✗
            </span>
          )}

          {/* Database Status */}
          {isDbChecking && (
            <span
              id="db-status-badge"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-50 text-slate-700 border border-slate-200"
            >
              <span className="relative inline-flex rounded-full h-2 w-2 bg-slate-400"></span>
              DB: Checking...
            </span>
          )}

          {isDbConnected && (
            <span
              id="db-status-badge"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200"
            >
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
              DB: Connected ✓
            </span>
          )}

          {isDbUnavailable && (
            <span
              id="db-status-badge"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200"
            >
              <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-600"></span>
              DB: Unavailable ✗
            </span>
          )}
        </div>
      </div>

      {/* Body / Metadata Grid */}
      <div className="py-6 space-y-4">
        {isBackendConnected && state.data && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 block">
                Target Service
              </span>
              <span className="text-base font-semibold text-slate-900 font-mono">
                {state.data.service}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 block">
                Environment
              </span>
              <span className="text-base font-semibold text-slate-900 capitalize">
                {state.data.environment}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 block">
                Service Version
              </span>
              <span className="text-base font-semibold text-slate-900 font-mono">
                v{state.data.version}
              </span>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500 block">
                Round-trip Latency
              </span>
              <span className="text-base font-semibold text-emerald-700 font-mono">
                {state.latencyMs !== null ? `${state.latencyMs} ms` : "—"}
              </span>
            </div>
          </div>
        )}

        {isBackendUnavailable && (
          <div
            id="error-diagnostic"
            className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 space-y-2"
          >
            <div className="font-semibold flex items-center gap-2">
              <svg
                className="w-5 h-5 text-rose-600 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>Cannot establish connection to FastAPI backend</span>
            </div>
            <p className="text-sm text-rose-700 pl-7">
              {state.errorMessage || "Network request failed"}
            </p>
          </div>
        )}

        {isBackendConnected && isDbUnavailable && (
          <div
            id="db-error-diagnostic"
            className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 space-y-1"
          >
            <div className="font-semibold flex items-center gap-2 text-sm">
              <span>⚠️ PostgreSQL Database is currently offline or unreachable</span>
            </div>
            <p className="text-xs text-amber-700">
              {state.databaseMessage || "Backend is running, but database connection could not be verified."}
            </p>
          </div>
        )}

        {/* Target Endpoint Info */}
        <div className="text-xs text-slate-400 flex flex-col sm:flex-row justify-between gap-1 pt-2 border-t border-slate-100">
          <div>
            <span className="font-medium text-slate-500">API Prefix: </span>
            <code className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-700">
              {config.apiBaseUrl}
            </code>
          </div>
          {state.lastChecked && (
            <div>
              <span className="font-medium text-slate-500">Last Checked: </span>
              {state.lastChecked.toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-4 border-t border-slate-100">
        <p className="text-xs text-slate-500">
          Click button to verify live API and PostgreSQL connectivity.
        </p>
        <button
          id="btn-recheck-health"
          onClick={onRefresh}
          disabled={isRefreshing || isBackendChecking}
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:ring-offset-2 min-h-[44px]"
        >
          {isRefreshing || isBackendChecking ? (
            <>
              <svg
                className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              Checking...
            </>
          ) : (
            <>
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Recheck Health
            </>
          )}
        </button>
      </div>
    </div>
  );
}
