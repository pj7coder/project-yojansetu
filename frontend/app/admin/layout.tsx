"use client";

import React, { useState, useEffect } from "react";
import { AdminSidebar } from "../../components/admin/AdminSidebar";
import { AdminHeader } from "../../components/admin/AdminHeader";
import { getAdminOverview } from "../../lib/api";
import { SystemStatusType } from "../../types/admin";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [systemStatus, setSystemStatus] = useState<SystemStatusType>("HEALTHY");
  const [statusReasons, setStatusReasons] = useState<string[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchStatus = async (forceRefresh: boolean = false) => {
    try {
      setIsRefreshing(true);
      const res = await getAdminOverview(forceRefresh);
      setSystemStatus(res.system_status);
      setStatusReasons(res.system_status_reasons || []);
    } catch (err) {
      console.error("Failed to load top-level system status:", err);
      setSystemStatus("CRITICAL");
      setStatusReasons(["Backend API is unreachable or reported critical error"]);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    // 60-second light polling for overview freshness
    const interval = setInterval(() => fetchStatus(false), 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-screen w-full bg-slate-100 flex text-slate-800 font-sans antialiased overflow-hidden">
      <AdminSidebar />
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <AdminHeader
          systemStatus={systemStatus}
          statusReasons={statusReasons}
          onRefresh={() => fetchStatus(true)}
          isRefreshing={isRefreshing}
        />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto space-y-6 pb-12">{children}</div>
        </main>
      </div>
    </div>
  );
}
