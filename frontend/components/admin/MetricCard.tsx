"use client";

import React from "react";
import Link from "next/link";

interface MetricCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  accent?: "neutral" | "emerald" | "amber" | "rose" | "sky";
  link?: string;
  alertBadge?: string;
}

export function MetricCard({
  title,
  value,
  subtitle,
  accent = "neutral",
  link,
  alertBadge,
}: MetricCardProps) {
  let borderClass = "border-slate-200 hover:border-slate-300";
  let valColor = "text-slate-900";

  if (accent === "emerald") {
    borderClass = "border-emerald-200 hover:border-emerald-300";
    valColor = "text-emerald-700";
  } else if (accent === "amber") {
    borderClass = "border-amber-200 hover:border-amber-300";
    valColor = "text-amber-700";
  } else if (accent === "rose") {
    borderClass = "border-rose-200 hover:border-rose-300";
    valColor = "text-rose-700";
  } else if (accent === "sky") {
    borderClass = "border-sky-200 hover:border-sky-300";
    valColor = "text-sky-700";
  }

  const content = (
    <div
      className={`bg-white rounded-lg border p-4 shadow-sm transition-all duration-150 relative ${borderClass}`}
    >
      {alertBadge && (
        <span className="absolute top-3 right-3 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200">
          {alertBadge}
        </span>
      )}
      <div className="text-xs font-medium uppercase tracking-wider text-slate-500 mb-1">
        {title}
      </div>
      <div className={`text-2xl font-bold tracking-tight ${valColor}`}>
        {value}
      </div>
      {subtitle && (
        <div className="text-xs text-slate-500 mt-1 font-normal">
          {subtitle}
        </div>
      )}
    </div>
  );

  if (link) {
    return (
      <Link href={link} className="block group">
        {content}
      </Link>
    );
  }

  return content;
}
