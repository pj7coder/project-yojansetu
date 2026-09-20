"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { SystemStatusType, AdminGlobalSearchResponse } from "../../types/admin";
import { adminGlobalSearch } from "../../lib/api";

interface AdminHeaderProps {
  systemStatus?: SystemStatusType;
  statusReasons?: string[];
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function AdminHeader({
  systemStatus = "HEALTHY",
  statusReasons = [],
  onRefresh,
  isRefreshing = false,
}: AdminHeaderProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<AdminGlobalSearchResponse | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [showReasonsModal, setShowReasonsModal] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  // Global search debounce
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      setShowDropdown(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await adminGlobalSearch(searchQuery.trim());
        setSearchResults(res);
        setShowDropdown(true);
      } catch (err) {
        console.error("Global search error:", err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Click outside listener for search results
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        searchContainerRef.current &&
        !searchContainerRef.current.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // System status styling
  let statusBadgeBg = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
  let statusDot = "bg-emerald-400";
  let statusText = "System Healthy";

  if (systemStatus === "WARNING") {
    statusBadgeBg = "bg-amber-500/10 text-amber-400 border-amber-500/30";
    statusDot = "bg-amber-400 animate-pulse";
    statusText = `System Warning (${statusReasons.length} issue${statusReasons.length === 1 ? "" : "s"})`;
  } else if (systemStatus === "CRITICAL") {
    statusBadgeBg = "bg-rose-500/10 text-rose-400 border-rose-500/30";
    statusDot = "bg-rose-400 animate-pulse";
    statusText = "System Critical";
  }

  return (
    <header className="h-14 bg-slate-900 border-b border-slate-800 px-6 flex items-center justify-between gap-4 sticky top-0 z-30">
      {/* Search Input */}
      <div className="relative flex-1 max-w-md" ref={searchContainerRef}>
        <div className="relative">
          <input
            type="text"
            placeholder="Global search schemes, documents, sources..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => {
              if (searchResults && searchResults.total_hits > 0) {
                setShowDropdown(true);
              }
            }}
            className="w-full h-8 pl-8 pr-3 text-xs bg-slate-800 text-slate-100 placeholder-slate-400 rounded border border-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          <span className="absolute left-2.5 top-2 text-slate-400 text-xs">🔍</span>
          {isSearching && (
            <span className="absolute right-2.5 top-2 text-slate-400 text-xs animate-spin">
              ⏳
            </span>
          )}
        </div>

        {/* Search Results Dropdown */}
        {showDropdown && searchResults && (
          <div className="absolute top-10 left-0 right-0 bg-slate-800 border border-slate-700 rounded-md shadow-xl max-h-96 overflow-y-auto z-50 text-xs text-slate-200 divide-y divide-slate-700">
            {searchResults.total_hits === 0 ? (
              <div className="p-3 text-center text-slate-400">No operational matches found</div>
            ) : (
              <>
                {searchResults.schemes.length > 0 && (
                  <div className="p-2">
                    <div className="text-[10px] font-semibold uppercase text-slate-400 px-2 py-1">
                      Schemes ({searchResults.schemes.length})
                    </div>
                    {searchResults.schemes.map((s) => (
                      <Link
                        key={s.id}
                        href={`/admin/schemes?query=${encodeURIComponent(s.title)}`}
                        onClick={() => setShowDropdown(false)}
                        className="block px-2 py-1.5 rounded hover:bg-slate-700"
                      >
                        <div className="font-semibold text-white">{s.title}</div>
                        <div className="text-[11px] text-slate-400">{s.code} • {s.status}</div>
                      </Link>
                    ))}
                  </div>
                )}

                {searchResults.documents.length > 0 && (
                  <div className="p-2">
                    <div className="text-[10px] font-semibold uppercase text-slate-400 px-2 py-1">
                      Documents ({searchResults.documents.length})
                    </div>
                    {searchResults.documents.map((d) => (
                      <Link
                        key={d.id}
                        href={`/admin/documents?query=${encodeURIComponent(d.code || d.title)}`}
                        onClick={() => setShowDropdown(false)}
                        className="block px-2 py-1.5 rounded hover:bg-slate-700"
                      >
                        <div className="font-semibold text-white">{d.title}</div>
                        <div className="text-[11px] text-slate-400">{d.code} • {d.status}</div>
                      </Link>
                    ))}
                  </div>
                )}

                {searchResults.sources.length > 0 && (
                  <div className="p-2">
                    <div className="text-[10px] font-semibold uppercase text-slate-400 px-2 py-1">
                      Sources ({searchResults.sources.length})
                    </div>
                    {searchResults.sources.map((src) => (
                      <Link
                        key={src.id}
                        href={`/admin/sources?query=${encodeURIComponent(src.title)}`}
                        onClick={() => setShowDropdown(false)}
                        className="block px-2 py-1.5 rounded hover:bg-slate-700"
                      >
                        <div className="font-semibold text-white">{src.title}</div>
                        <div className="text-[11px] text-slate-400">{src.subtitle} • {src.status}</div>
                      </Link>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* System Health Pill */}
        <button
          type="button"
          onClick={() => statusReasons.length > 0 && setShowReasonsModal(!showReasonsModal)}
          className={`flex items-center gap-2 px-2.5 py-1 rounded-full border text-xs font-medium cursor-pointer transition ${statusBadgeBg}`}
          title={statusReasons.length > 0 ? "Click to view reasons" : "System operates within healthy limits"}
        >
          <span className={`w-2 h-2 rounded-full ${statusDot}`} />
          <span>{statusText}</span>
          {statusReasons.length > 0 && <span className="text-[10px]">▼</span>}
        </button>

        {/* Manual Refresh Button */}
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 text-xs text-slate-300 hover:text-white px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 transition disabled:opacity-50"
            title="Refresh dashboard metrics"
          >
            <span className={isRefreshing ? "animate-spin" : ""}>🔄</span>
            <span>Refresh</span>
          </button>
        )}
      </div>

      {/* Status Reasons Flyout */}
      {showReasonsModal && statusReasons.length > 0 && (
        <div className="absolute top-14 right-6 w-80 bg-slate-800 border border-slate-700 rounded-md shadow-2xl p-4 text-xs z-50 text-slate-200">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-700">
            <span className="font-semibold text-white">Active System Observations</span>
            <button
              onClick={() => setShowReasonsModal(false)}
              className="text-slate-400 hover:text-white"
            >
              ✕
            </button>
          </div>
          <ul className="space-y-1.5 list-disc pl-4 text-slate-300">
            {statusReasons.map((reason, idx) => (
              <li key={idx} className="leading-relaxed">{reason}</li>
            ))}
          </ul>
        </div>
      )}
    </header>
  );
}
