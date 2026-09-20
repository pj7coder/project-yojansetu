"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  name: string;
  href: string;
  icon: string;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { name: "Overview", href: "/admin", icon: "📊" },
  { name: "Sources", href: "/admin/sources", icon: "🌐" },
  { name: "Documents", href: "/admin/documents", icon: "📄" },
  { name: "Processing", href: "/admin/processing", icon: "⚙️" },
  { name: "Reviews", href: "/admin/review", icon: "🔍" },
  { name: "Schemes", href: "/admin/schemes", icon: "📋" },
  { name: "Versions", href: "/admin/versions", icon: "⏳" },
  { name: "Conflicts", href: "/admin/conflicts", icon: "⚠️" },
  { name: "System", href: "/admin/system", icon: "🖥️" },
];

export function AdminSidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-slate-900 text-slate-200 flex flex-col flex-shrink-0 border-r border-slate-800 min-h-screen">
      {/* Brand & Identity */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <Link href="/admin" className="flex items-center gap-2.5">
          <span className="text-xl">🛡️</span>
          <div>
            <div className="font-bold text-sm text-white tracking-tight">YojanSetu</div>
            <div className="text-[11px] text-slate-400 font-mono">Operations Control</div>
          </div>
        </Link>
        <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
          v5.0
        </span>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/admin"
              ? pathname === "/admin"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                isActive
                  ? "bg-blue-600 text-white font-semibold"
                  : "text-slate-300 hover:bg-slate-800 hover:text-white"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <span className="text-sm">{item.icon}</span>
                <span>{item.name}</span>
              </div>
              {item.badge && (
                <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-slate-800 text-slate-300">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer / Operator Status */}
      <div className="p-3 border-t border-slate-800 text-xs text-slate-400 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px]">Actor:</span>
          <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
            DEV_REVIEWER
          </span>
        </div>
        <div className="flex items-center justify-between text-[11px]">
          <span>Interface:</span>
          <Link href="/citizen" className="text-blue-400 hover:text-blue-300 underline">
            Citizen Mode ↗
          </Link>
        </div>
      </div>
    </aside>
  );
}
