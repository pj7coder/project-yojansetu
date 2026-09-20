"use client";

import React from "react";
import Link from "next/link";
import { AdminActivityItem } from "../../types/admin";

interface RecentActivityProps {
  items: AdminActivityItem[];
}

export function RecentActivity({ items }: RecentActivityProps) {
  if (!items || items.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm text-center text-xs text-slate-500">
        No recent operational events recorded.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
        <h2 className="text-sm font-bold text-slate-900 tracking-tight">
          Recent Operational Activity
        </h2>
        <span className="text-[11px] text-slate-500 font-mono">
          System & Pipeline Events (Privacy Verified)
        </span>
      </div>

      <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto pr-1">
        {items.map((act) => {
          let dotColor = "bg-slate-400";
          if (act.severity === "SUCCESS") dotColor = "bg-emerald-500";
          else if (act.severity === "WARNING") dotColor = "bg-amber-500";
          else if (act.severity === "ERROR" || act.severity === "CRITICAL") dotColor = "bg-rose-500";

          const formattedTime = new Date(act.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          });
          const formattedDate = new Date(act.timestamp).toLocaleDateString([], {
            month: "short",
            day: "numeric",
          });

          return (
            <div key={act.id} className="py-2.5 flex items-start justify-between gap-3 text-xs">
              <div className="flex items-start gap-2.5">
                <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${dotColor}`} />
                <div>
                  <div className="font-semibold text-slate-900">
                    {act.title}
                  </div>
                  <div className="text-slate-600 mt-0.5">
                    {act.description}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-0.5">
                    Actor: {act.actor} • Type: {act.event_type}
                  </div>
                </div>
              </div>

              <div className="text-right flex-shrink-0">
                <div className="font-mono text-[11px] text-slate-500">
                  {formattedTime}
                </div>
                <div className="text-[10px] text-slate-400">
                  {formattedDate}
                </div>
                {act.target_link && (
                  <Link
                    href={act.target_link}
                    className="text-[11px] text-blue-600 hover:text-blue-800 font-medium underline mt-1 block"
                  >
                    View →
                  </Link>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
