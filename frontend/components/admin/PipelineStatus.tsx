"use client";

import React from "react";
import Link from "next/link";
import { PipelineStageCount } from "../../types/admin";

interface PipelineStatusProps {
  stages: PipelineStageCount[];
}

export function PipelineStatus({ stages }: PipelineStatusProps) {
  if (!stages || stages.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-4 text-xs text-slate-500 text-center">
        No active pipeline stages recorded.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-bold text-slate-900 tracking-tight">
            Pipeline Workload Distribution
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time queue depth across 10 deterministic processing stages
          </p>
        </div>
        <Link
          href="/admin/processing"
          className="text-xs font-semibold text-blue-600 hover:text-blue-700 underline"
        >
          View Queue Details →
        </Link>
      </div>

      {/* Horizontal Pipeline Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
        {stages.map((st, idx) => {
          const hasWaiting = st.waiting > 0;
          const hasProcessing = st.processing > 0;
          const hasFailed = st.failed > 0;

          let cardBg = "bg-slate-50 border-slate-200";
          if (hasFailed) cardBg = "bg-rose-50 border-rose-200";
          else if (hasProcessing) cardBg = "bg-blue-50 border-blue-200";
          else if (hasWaiting) cardBg = "bg-amber-50 border-amber-200";

          return (
            <div
              key={st.stage}
              className={`p-2.5 rounded-md border text-center relative flex flex-col justify-between ${cardBg}`}
            >
              <div className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1 truncate" title={st.stage}>
                {idx + 1}. {st.stage}
              </div>

              <div className="space-y-1 my-1">
                <div className="text-base font-bold text-slate-900">
                  {st.waiting + st.processing}
                </div>
                <div className="text-[10px] text-slate-500 flex justify-center gap-1.5 font-mono">
                  <span title="Waiting">{st.waiting}w</span>
                  <span>•</span>
                  <span title="Active Processing">{st.processing}p</span>
                </div>
              </div>

              {hasFailed ? (
                <div className="text-[10px] font-semibold text-rose-700 bg-rose-100/70 rounded py-0.5 mt-1">
                  {st.failed} failed
                </div>
              ) : (
                <div className="text-[10px] text-emerald-700 bg-emerald-100/50 rounded py-0.5 mt-1 font-medium">
                  nominal
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
