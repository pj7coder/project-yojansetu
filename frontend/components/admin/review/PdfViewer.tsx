"use client";

import React, { useState, useEffect } from "react";
import { config } from "../../../lib/config";

interface PdfViewerProps {
  documentId: string;
  targetPage?: number | null;
  filename?: string;
}

export function PdfViewer({ documentId, targetPage, filename }: PdfViewerProps) {
  const [currentPage, setCurrentPage] = useState<number>(targetPage || 1);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  useEffect(() => {
    if (targetPage && targetPage > 0) {
      setCurrentPage(targetPage);
    }
  }, [targetPage]);

  const pdfUrl = `${config.apiBaseUrl}/documents/${documentId}/file#page=${currentPage}`;

  return (
    <div
      className={`flex flex-col bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg h-full ${
        isFullscreen ? "fixed inset-0 z-50 rounded-none" : ""
      }`}
    >
      {/* Top Controls Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-950 border-b border-slate-800 text-xs text-slate-300">
        <div className="flex items-center gap-2 truncate">
          <span className="font-semibold text-white truncate max-w-[200px] sm:max-w-xs" title={filename || "Original Document"}>
            📄 {filename || "Original Document"}
          </span>
          <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 font-mono text-[11px]">
            Physical Page: {currentPage}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick Page Steppers */}
          <div className="flex items-center bg-slate-900 border border-slate-700 rounded">
            <button
              type="button"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="px-2 py-1 text-slate-400 hover:text-white disabled:opacity-30 transition"
              title="Previous Page"
            >
              ◀
            </button>
            <span className="px-2 font-mono text-slate-200">p.{currentPage}</span>
            <button
              type="button"
              onClick={() => setCurrentPage((p) => p + 1)}
              className="px-2 py-1 text-slate-400 hover:text-white transition"
              title="Next Page"
            >
              ▶
            </button>
          </div>

          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
            title="Open in new window"
          >
            Open Tab ↗
          </a>

          <button
            type="button"
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            {isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
          </button>
        </div>
      </div>

      {/* PDF Viewport */}
      <div className="relative flex-1 w-full bg-slate-900 min-h-[500px]">
        <iframe
          key={`${documentId}-page-${currentPage}`}
          src={pdfUrl}
          className="w-full h-full border-0"
          title={`PDF Preview - Page ${currentPage}`}
        />
      </div>
    </div>
  );
}
