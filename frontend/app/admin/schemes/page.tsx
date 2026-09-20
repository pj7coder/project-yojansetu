"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  getAdminSchemes,
  getSchemeDetail,
  updateSchemeFull,
  deleteScheme,
  ApiError,
} from "../../../lib/api";
import {
  AdminSchemeListItem,
  SchemeDetailResponse,
  CanonicalBenefit,
  EligibilityCondition,
  CanonicalDocument,
} from "../../../types/admin";
import { StatusBadge } from "../../../components/admin/StatusBadge";

export default function AdminSchemesPage() {
  const [schemes, setSchemes] = useState<AdminSchemeListItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(25);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Inspector & Editor Modal State
  const [selectedSchemeId, setSelectedSchemeId] = useState<string | null>(null);
  const [schemeDetail, setSchemeDetail] = useState<SchemeDetailResponse | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"overview" | "benefits" | "eligibility" | "documents" | "application" | "evidence">("overview");

  // Editable form state for modal
  const [editForm, setEditForm] = useState<{
    scheme_code: string;
    name_en: string;
    name_hi: string;
    short_name: string;
    short_description: string;
    status: string;
    origin: string;
    jurisdiction: string;
    benefits: CanonicalBenefit[];
    simple_fields: Record<string, any>;
    conditions: EligibilityCondition[];
    exclusions: Array<{ field?: string; raw_text?: string }>;
    required_documents: CanonicalDocument[];
    application_channels: string[];
    portal_url: string;
    office: string;
    application_steps: string[];
    fees: string;
    application_window: string;
  }>({
    scheme_code: "",
    name_en: "",
    name_hi: "",
    short_name: "",
    short_description: "",
    status: "ACTIVE",
    origin: "RAJASTHAN_STATE",
    jurisdiction: "RAJASTHAN",
    benefits: [],
    simple_fields: {},
    conditions: [],
    exclusions: [],
    required_documents: [],
    application_channels: ["ONLINE", "EMITRA"],
    portal_url: "",
    office: "",
    application_steps: [],
    fees: "",
    application_window: "",
  });

  const loadSchemes = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getAdminSchemes({
        status: statusFilter || undefined,
        query: searchQuery.trim() || undefined,
        page,
        page_size: pageSize,
      });
      setSchemes(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      console.error("Failed to load schemes:", err);
      setError(err.message || "Failed to load verified schemes.");
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, searchQuery, page, pageSize]);

  useEffect(() => {
    loadSchemes();
  }, [loadSchemes]);

  // Handle opening Scheme Inspector & Editor
  const handleOpenInspector = async (schemeId: string) => {
    setSelectedSchemeId(schemeId);
    setIsLoadingDetail(true);
    setDetailError(null);
    setActiveTab("overview");

    try {
      const detail = await getSchemeDetail(schemeId);
      setSchemeDetail(detail);

      const canonical = detail.canonical_data || {};
      const identity = canonical.scheme_identity || {};
      const identityName = identity.name || {};
      const benefits = Array.isArray(canonical.benefits) ? canonical.benefits : [];
      const eligibility = canonical.eligibility || {};
      const simpleFields = eligibility.simple_fields || {};
      const conditions = Array.isArray(eligibility.conditions) ? eligibility.conditions : [];
      const exclusions = Array.isArray(eligibility.exclusions) ? eligibility.exclusions : [];
      const reqDocs = Array.isArray(canonical.required_documents) ? canonical.required_documents : [];
      const appInfo = canonical.application || {};

      setEditForm({
        scheme_code: detail.scheme_code || "",
        name_en: detail.name_en || identityName.en || "",
        name_hi: detail.name_hi || identityName.hi || "",
        short_name: detail.short_name || identityName.short_name || "",
        short_description: detail.short_description || identity.description || "",
        status: detail.status || "ACTIVE",
        origin: detail.scheme_origin || "RAJASTHAN_STATE",
        jurisdiction: detail.jurisdiction || "RAJASTHAN",
        benefits: JSON.parse(JSON.stringify(benefits)),
        simple_fields: JSON.parse(JSON.stringify(simpleFields)),
        conditions: JSON.parse(JSON.stringify(conditions)),
        exclusions: JSON.parse(JSON.stringify(exclusions)),
        required_documents: JSON.parse(JSON.stringify(reqDocs)),
        application_channels: Array.isArray(appInfo.channels) ? [...appInfo.channels] : ["ONLINE", "EMITRA"],
        portal_url: appInfo.portal_url || "",
        office: appInfo.office || "",
        application_steps: Array.isArray(appInfo.steps) ? [...appInfo.steps] : [],
        fees: appInfo.fees || "",
        application_window: appInfo.application_window || "",
      });
    } catch (err: any) {
      console.error("Failed to load scheme details:", err);
      setDetailError(err.message || "Failed to load scheme details.");
    } finally {
      setIsLoadingDetail(false);
    }
  };

  // Handle Saving Scheme Edits
  const handleSaveScheme = async () => {
    if (!selectedSchemeId || !schemeDetail) return;
    setIsSaving(true);
    setDetailError(null);

    try {
      const updatePayload = {
        scheme_code: editForm.scheme_code.trim(),
        name_en: editForm.name_en.trim(),
        name_hi: editForm.name_hi.trim() || null,
        short_name: editForm.short_name.trim() || null,
        short_description: editForm.short_description.trim() || null,
        status: editForm.status,
        scheme_origin: editForm.origin,
        jurisdiction: editForm.jurisdiction,
        benefits: editForm.benefits,
        eligibility: {
          simple_fields: editForm.simple_fields,
          conditions: editForm.conditions,
          exclusions: editForm.exclusions,
        },
        required_documents: editForm.required_documents,
        application: {
          channels: editForm.application_channels,
          portal_url: editForm.portal_url || null,
          office: editForm.office || null,
          steps: editForm.application_steps,
          fees: editForm.fees || null,
          application_window: editForm.application_window || null,
        },
      };

      const updated = await updateSchemeFull(selectedSchemeId, updatePayload);
      setSchemeDetail(updated);
      setActionSuccess(`Scheme '${updated.name_en}' updated successfully in the database!`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadSchemes();
    } catch (err: any) {
      console.error("Failed to update scheme:", err);
      setDetailError(err.message || "Failed to update scheme.");
    } finally {
      setIsSaving(false);
    }
  };

  // Quick toggle Active status
  const handleToggleStatus = async (scheme: AdminSchemeListItem) => {
    const newStatus = scheme.is_active ? "INACTIVE" : "ACTIVE";
    try {
      await updateSchemeFull(scheme.id, { status: newStatus });
      setActionSuccess(`Status for '${scheme.name_en}' changed to ${newStatus}`);
      setTimeout(() => setActionSuccess(null), 3000);
      loadSchemes();
    } catch (err: any) {
      alert(`Failed to update status: ${err.message}`);
    }
  };

  // Delete scheme
  const handleDeleteScheme = async (scheme: AdminSchemeListItem) => {
    if (!confirm(`Are you sure you want to permanently delete scheme '${scheme.name_en}' (${scheme.scheme_code})?`)) {
      return;
    }
    try {
      await deleteScheme(scheme.id);
      setActionSuccess(`Scheme '${scheme.name_en}' deleted successfully.`);
      if (selectedSchemeId === scheme.id) {
        setSelectedSchemeId(null);
        setSchemeDetail(null);
      }
      setTimeout(() => setActionSuccess(null), 3000);
      loadSchemes();
    } catch (err: any) {
      alert(`Failed to delete scheme: ${err.message}`);
    }
  };

  // Benefit Helpers
  const addBenefit = () => {
    setEditForm((prev) => ({
      ...prev,
      benefits: [
        ...prev.benefits,
        {
          type: "SUBSIDY",
          amount: 1000,
          currency: "INR",
          frequency: "MONTHLY",
          description: "New benefit entitlement",
          raw_text: "",
        },
      ],
    }));
  };

  const removeBenefit = (index: number) => {
    setEditForm((prev) => ({
      ...prev,
      benefits: prev.benefits.filter((_, i) => i !== index),
    }));
  };

  // Condition Helpers
  const addCondition = () => {
    setEditForm((prev) => ({
      ...prev,
      conditions: [
        ...prev.conditions,
        {
          condition_id: `COND-${Date.now().toString().slice(-4)}`,
          field: "age",
          operator: "GTE",
          value: 18,
          raw_text: "Applicant must meet age requirement",
        },
      ],
    }));
  };

  const removeCondition = (index: number) => {
    setEditForm((prev) => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index),
    }));
  };

  // Document Helpers
  const addDocument = () => {
    setEditForm((prev) => ({
      ...prev,
      required_documents: [
        ...prev.required_documents,
        {
          document_id: `DOC-${Date.now().toString().slice(-4)}`,
          document_type: "AADHAAR",
          name_raw: "Aadhaar Card",
          mandatory: true,
          notes: "Identity proof",
        },
      ],
    }));
  };

  const removeDocument = (index: number) => {
    setEditForm((prev) => ({
      ...prev,
      required_documents: prev.required_documents.filter((_, i) => i !== index),
    }));
  };

  // Application Step Helpers
  const addApplicationStep = () => {
    setEditForm((prev) => ({
      ...prev,
      application_steps: [...prev.application_steps, "New application procedure step"],
    }));
  };

  const removeApplicationStep = (index: number) => {
    setEditForm((prev) => ({
      ...prev,
      application_steps: prev.application_steps.filter((_, i) => i !== index),
    }));
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Command Center Header */}
      <div className="bg-white rounded-xl shadow-xs border border-slate-200 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="text-2xl">📋</span>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              Official Schemes & Rule Repository
            </h1>
            <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-blue-100 text-blue-800 border border-blue-200">
              Direct DB Published
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Live database schemes powering Rajasthan citizen voice discovery and deterministic eligibility. Inspect all extracted details, benefits, criteria, and edit any field in real-time.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/admin/documents"
            className="text-xs font-semibold px-3 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition flex items-center gap-1.5"
          >
            <span>📁</span>
            <span>Upload Document</span>
          </Link>
          <button
            onClick={() => loadSchemes()}
            disabled={isLoading}
            className="text-xs font-semibold px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition shadow-xs flex items-center gap-1.5"
          >
            <span>↻</span>
            <span>Refresh Schemes</span>
          </button>
        </div>
      </div>

      {/* Success Alert */}
      {actionSuccess && (
        <div className="p-3.5 text-xs bg-emerald-50 border border-emerald-300 text-emerald-900 rounded-lg flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <span className="text-base">✓</span>
            <span className="font-semibold">{actionSuccess}</span>
          </div>
          <button onClick={() => setActionSuccess(null)} className="text-emerald-700 hover:text-emerald-900 font-bold">✕</button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="p-3.5 text-xs bg-rose-50 border border-rose-200 text-rose-800 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-base">⚠️</span>
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-700 hover:text-rose-900 font-bold">✕</button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Total Schemes in DB</div>
          <div className="text-2xl font-bold text-slate-900 mt-1">{total}</div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-600">Active Schemes</div>
          <div className="text-2xl font-bold text-emerald-700 mt-1">
            {schemes.filter((s) => s.is_active).length}
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-blue-600">Rajasthan State Schemes</div>
          <div className="text-2xl font-bold text-blue-700 mt-1">
            {schemes.filter((s) => s.scheme_origin === "RAJASTHAN_STATE").length}
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-purple-600">Central / CSS Schemes</div>
          <div className="text-2xl font-bold text-purple-700 mt-1">
            {schemes.filter((s) => s.scheme_origin !== "RAJASTHAN_STATE").length}
          </div>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative flex-1 w-full">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400 text-sm">
            🔍
          </span>
          <input
            type="text"
            placeholder="Search by Scheme Name (English / Hindi), Code (e.g. RJ-GEN-PMKUSUM), or Department..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-xs py-2 px-3 rounded-lg border border-slate-300 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="HUMAN_VERIFIED">HUMAN_VERIFIED</option>
            <option value="DRAFT">DRAFT</option>
            <option value="INACTIVE">INACTIVE</option>
          </select>
        </div>
      </div>

      {/* Schemes List Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-xs text-slate-500">
            <div className="inline-block animate-spin text-2xl mb-2">↻</div>
            <div>Loading schemes from database...</div>
          </div>
        ) : schemes.length === 0 ? (
          <div className="p-12 text-center text-slate-500 space-y-2">
            <div className="text-3xl">📭</div>
            <div className="font-semibold text-slate-800">No schemes matched your criteria</div>
            <p className="text-xs text-slate-400">
              Upload a government PDF circular in the Documents section or drop a PDF into the watch folder to automatically extract and publish schemes.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase text-[10px] tracking-wider font-semibold">
                  <th className="py-3 px-4">Scheme Code & Title</th>
                  <th className="py-3 px-4">Department</th>
                  <th className="py-3 px-4">Origin</th>
                  <th className="py-3 px-4">Version</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {schemes.map((s) => (
                  <tr key={s.id} className="hover:bg-blue-50/40 transition">
                    <td className="py-3.5 px-4">
                      <div className="space-y-0.5">
                        <div className="font-bold text-slate-900 text-[13px]">{s.name_en}</div>
                        {s.name_hi && (
                          <div className="text-[11px] text-slate-600 font-hindi">{s.name_hi}</div>
                        )}
                        <div className="text-[10px] font-mono text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded inline-block font-semibold">
                          {s.scheme_code}
                        </div>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-slate-700 font-medium">
                      {s.department_name || "General Administration"}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                        {s.scheme_origin}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-[11px] font-mono font-bold text-blue-700">
                        {s.current_version_number ? `v${s.current_version_number}` : "v1"}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={s.is_active ? "ACTIVE" : "INACTIVE"} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-2 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => handleOpenInspector(s.id)}
                        className="px-2.5 py-1 text-xs font-semibold rounded bg-blue-600 hover:bg-blue-700 text-white transition shadow-xs"
                      >
                        Inspect & Edit Details →
                      </button>
                      <button
                        type="button"
                        onClick={() => handleToggleStatus(s)}
                        className="px-2 py-1 text-xs rounded border border-slate-300 hover:bg-slate-100 text-slate-600 transition"
                        title="Toggle Active / Inactive"
                      >
                        {s.is_active ? "Deactivate" : "Activate"}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteScheme(s)}
                        className="px-2 py-1 text-xs rounded text-rose-600 hover:bg-rose-50 border border-rose-200 transition"
                        title="Delete Scheme"
                      >
                        🗑
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* Comprehensive Scheme Inspector & In-Place Editor Modal                     */}
      {/* ========================================================================= */}
      {selectedSchemeId && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex justify-center items-center p-3 sm:p-6">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="px-6 py-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
              <div className="flex items-center gap-3">
                <span className="text-xl">📋</span>
                <div>
                  <div className="text-sm font-bold text-white flex items-center gap-2">
                    <span>{editForm.name_en || "Scheme Inspector"}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-900 text-blue-300 border border-blue-700">
                      {editForm.scheme_code || "CODE"}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Direct Database Editor • Changes immediately update search and citizen eligibility
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedSchemeId(null)}
                  className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center transition font-bold"
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Modal Navigation Tabs */}
            <div className="bg-slate-100 px-6 border-b border-slate-200 flex space-x-1 overflow-x-auto text-xs font-semibold">
              <button
                type="button"
                onClick={() => setActiveTab("overview")}
                className={`py-3 px-3.5 border-b-2 transition whitespace-nowrap ${
                  activeTab === "overview"
                    ? "border-blue-600 text-blue-700 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                1. Overview & Identity
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("benefits")}
                className={`py-3 px-3.5 border-b-2 transition whitespace-nowrap ${
                  activeTab === "benefits"
                    ? "border-blue-600 text-blue-700 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                2. Benefits & Subsidies ({editForm.benefits.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("eligibility")}
                className={`py-3 px-3.5 border-b-2 transition whitespace-nowrap ${
                  activeTab === "eligibility"
                    ? "border-blue-600 text-blue-700 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                3. Eligibility & Rules ({editForm.conditions.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("documents")}
                className={`py-3 px-3.5 border-b-2 transition whitespace-nowrap ${
                  activeTab === "documents"
                    ? "border-blue-600 text-blue-700 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                4. Required Documents ({editForm.required_documents.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("application")}
                className={`py-3 px-3.5 border-b-2 transition whitespace-nowrap ${
                  activeTab === "application"
                    ? "border-blue-600 text-blue-700 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                5. Application Process
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("evidence")}
                className={`py-3 px-3.5 border-b-2 transition whitespace-nowrap ${
                  activeTab === "evidence"
                    ? "border-blue-600 text-blue-700 bg-white"
                    : "border-transparent text-slate-600 hover:text-slate-900"
                }`}
              >
                6. PDF Evidence Snippets
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 text-xs text-slate-800 space-y-6">
              {isLoadingDetail ? (
                <div className="py-16 text-center text-slate-500">
                  <div className="animate-spin text-3xl mb-3">↻</div>
                  <div>Loading complete scheme details & rules...</div>
                </div>
              ) : detailError ? (
                <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-lg">
                  {detailError}
                </div>
              ) : (
                <>
                  {/* TAB 1: OVERVIEW & IDENTITY */}
                  {activeTab === "overview" && (
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Scheme Code / Machine ID *</label>
                          <input
                            type="text"
                            value={editForm.scheme_code}
                            onChange={(e) => setEditForm({ ...editForm, scheme_code: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 font-mono text-xs focus:ring-2 focus:ring-blue-500"
                            placeholder="e.g. RJ-HEALTH-MAAY"
                          />
                          <p className="text-[10px] text-slate-400 mt-1">Unique machine-readable identifier in database.</p>
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Status</label>
                          <select
                            value={editForm.status}
                            onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs bg-white focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="ACTIVE">ACTIVE (Citizen Discoverable)</option>
                            <option value="HUMAN_VERIFIED">HUMAN_VERIFIED</option>
                            <option value="DRAFT">DRAFT</option>
                            <option value="INACTIVE">INACTIVE</option>
                            <option value="ARCHIVED">ARCHIVED</option>
                          </select>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Official English Name *</label>
                          <input
                            type="text"
                            value={editForm.name_en}
                            onChange={(e) => setEditForm({ ...editForm, name_en: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs focus:ring-2 focus:ring-blue-500"
                            placeholder="e.g. Mukhyamantri Ayushman Arogya Yojana"
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Official Hindi Name (Devanagari)</label>
                          <input
                            type="text"
                            value={editForm.name_hi}
                            onChange={(e) => setEditForm({ ...editForm, name_hi: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs font-hindi focus:ring-2 focus:ring-blue-500"
                            placeholder="e.g. मुख्यमंत्री आयुष्मान आरोग्य योजना"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Short Name / Acronym</label>
                          <input
                            type="text"
                            value={editForm.short_name}
                            onChange={(e) => setEditForm({ ...editForm, short_name: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs focus:ring-2 focus:ring-blue-500"
                            placeholder="e.g. MAAY / Chiranjeevi"
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Scheme Origin</label>
                          <select
                            value={editForm.origin}
                            onChange={(e) => setEditForm({ ...editForm, origin: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs bg-white"
                          >
                            <option value="RAJASTHAN_STATE">RAJASTHAN_STATE</option>
                            <option value="CENTRAL">CENTRAL</option>
                            <option value="CENTRALLY_SPONSORED">CENTRALLY_SPONSORED</option>
                            <option value="RAJASTHAN_MODIFIED_CSS">RAJASTHAN_MODIFIED_CSS</option>
                            <option value="UNKNOWN">UNKNOWN</option>
                          </select>
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Jurisdiction</label>
                          <input
                            type="text"
                            value={editForm.jurisdiction}
                            onChange={(e) => setEditForm({ ...editForm, jurisdiction: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block font-bold text-slate-700 mb-1">Scheme Objective & Description</label>
                        <textarea
                          rows={4}
                          value={editForm.short_description}
                          onChange={(e) => setEditForm({ ...editForm, short_description: e.target.value })}
                          className="w-full p-2.5 rounded border border-slate-300 text-xs focus:ring-2 focus:ring-blue-500"
                          placeholder="Provide a concise description of scheme objectives, targeted beneficiaries, and key deliverables..."
                        />
                      </div>
                    </div>
                  )}

                  {/* TAB 2: BENEFITS & SUBSIDIES */}
                  {activeTab === "benefits" && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                        <div>
                          <h3 className="font-bold text-slate-900">Extracted Benefits & Financial Entitlements</h3>
                          <p className="text-[11px] text-slate-500">Exact monetary amounts, pensions, scholarships, subsidies, or services provided to eligible citizens.</p>
                        </div>
                        <button
                          type="button"
                          onClick={addBenefit}
                          className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-700 text-white font-semibold flex items-center gap-1 shadow-xs"
                        >
                          + Add Benefit
                        </button>
                      </div>

                      {editForm.benefits.length === 0 ? (
                        <div className="p-8 text-center text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-300">
                          No benefits listed. Click &quot;+ Add Benefit&quot; to configure entitlements.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {editForm.benefits.map((b, idx) => (
                            <div key={idx} className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3 relative">
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-slate-700 text-[11px]">Benefit Item #{idx + 1}</span>
                                <button
                                  type="button"
                                  onClick={() => removeBenefit(idx)}
                                  className="text-rose-600 hover:text-rose-800 text-xs font-bold"
                                >
                                  ✕ Remove
                                </button>
                              </div>

                              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                                <div>
                                  <label className="block text-[10px] font-bold text-slate-500 mb-0.5">Benefit Type</label>
                                  <select
                                    value={b.type || "CASH"}
                                    onChange={(e) => {
                                      const updated = [...editForm.benefits];
                                      updated[idx].type = e.target.value;
                                      setEditForm({ ...editForm, benefits: updated });
                                    }}
                                    className="w-full p-2 rounded border border-slate-300 bg-white"
                                  >
                                    <option value="CASH">CASH</option>
                                    <option value="PENSION">PENSION</option>
                                    <option value="SUBSIDY">SUBSIDY</option>
                                    <option value="SCHOLARSHIP">SCHOLARSHIP</option>
                                    <option value="INSURANCE">INSURANCE</option>
                                    <option value="LOAN">LOAN</option>
                                    <option value="IN_KIND">IN_KIND</option>
                                    <option value="SERVICE">SERVICE</option>
                                    <option value="CONCESSION">CONCESSION</option>
                                    <option value="OTHER">OTHER</option>
                                  </select>
                                </div>

                                <div>
                                  <label className="block text-[10px] font-bold text-slate-500 mb-0.5">Amount (₹ or Quantity)</label>
                                  <input
                                    type="number"
                                    value={b.amount ?? ""}
                                    onChange={(e) => {
                                      const updated = [...editForm.benefits];
                                      updated[idx].amount = e.target.value ? parseFloat(e.target.value) : null;
                                      setEditForm({ ...editForm, benefits: updated });
                                    }}
                                    className="w-full p-2 rounded border border-slate-300"
                                    placeholder="e.g. 50000"
                                  />
                                </div>

                                <div>
                                  <label className="block text-[10px] font-bold text-slate-500 mb-0.5">Frequency</label>
                                  <select
                                    value={b.frequency || "ONE_TIME"}
                                    onChange={(e) => {
                                      const updated = [...editForm.benefits];
                                      updated[idx].frequency = e.target.value;
                                      setEditForm({ ...editForm, benefits: updated });
                                    }}
                                    className="w-full p-2 rounded border border-slate-300 bg-white"
                                  >
                                    <option value="ONE_TIME">ONE_TIME</option>
                                    <option value="MONTHLY">MONTHLY</option>
                                    <option value="ANNUAL">ANNUAL</option>
                                    <option value="PER_SEMESTER">PER_SEMESTER</option>
                                    <option value="PER_BENEFICIARY">PER_BENEFICIARY</option>
                                    <option value="UNKNOWN">UNKNOWN</option>
                                  </select>
                                </div>

                                <div>
                                  <label className="block text-[10px] font-bold text-slate-500 mb-0.5">Currency / Unit</label>
                                  <input
                                    type="text"
                                    value={b.currency || "INR"}
                                    onChange={(e) => {
                                      const updated = [...editForm.benefits];
                                      updated[idx].currency = e.target.value;
                                      setEditForm({ ...editForm, benefits: updated });
                                    }}
                                    className="w-full p-2 rounded border border-slate-300"
                                  />
                                </div>
                              </div>

                              <div>
                                <label className="block text-[10px] font-bold text-slate-500 mb-0.5">Benefit Description</label>
                                <input
                                  type="text"
                                  value={b.description || ""}
                                  onChange={(e) => {
                                    const updated = [...editForm.benefits];
                                    updated[idx].description = e.target.value;
                                    setEditForm({ ...editForm, benefits: updated });
                                  }}
                                  className="w-full p-2 rounded border border-slate-300"
                                  placeholder="Explanation of entitlement..."
                                />
                              </div>

                              {b.raw_text && (
                                <div className="p-2 rounded bg-amber-50/70 border border-amber-200 text-[10px] text-amber-900 font-mono">
                                  <span className="font-bold">Raw PDF Clause: </span>
                                  {b.raw_text}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 3: ELIGIBILITY & RULES */}
                  {activeTab === "eligibility" && (
                    <div className="space-y-6">
                      {/* Simple Field Constraints */}
                      <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/40 space-y-3">
                        <h4 className="font-bold text-blue-950 text-xs">Standard Citizen Demographic Constraints</h4>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                          <div>
                            <label className="block text-[10px] font-bold text-slate-600 mb-0.5">Minimum Age (years)</label>
                            <input
                              type="number"
                              value={editForm.simple_fields.min_age ?? ""}
                              onChange={(e) => setEditForm({
                                ...editForm,
                                simple_fields: { ...editForm.simple_fields, min_age: e.target.value ? parseInt(e.target.value) : undefined }
                              })}
                              className="w-full p-2 rounded border border-slate-300 bg-white"
                              placeholder="e.g. 18"
                            />
                          </div>

                          <div>
                            <label className="block text-[10px] font-bold text-slate-600 mb-0.5">Maximum Age (years)</label>
                            <input
                              type="number"
                              value={editForm.simple_fields.max_age ?? ""}
                              onChange={(e) => setEditForm({
                                ...editForm,
                                simple_fields: { ...editForm.simple_fields, max_age: e.target.value ? parseInt(e.target.value) : undefined }
                              })}
                              className="w-full p-2 rounded border border-slate-300 bg-white"
                              placeholder="e.g. 60"
                            />
                          </div>

                          <div>
                            <label className="block text-[10px] font-bold text-slate-600 mb-0.5">Family Income Cap (₹/year)</label>
                            <input
                              type="number"
                              value={editForm.simple_fields.family_income_max ?? editForm.simple_fields.annual_income_max ?? ""}
                              onChange={(e) => setEditForm({
                                ...editForm,
                                simple_fields: { ...editForm.simple_fields, family_income_max: e.target.value ? parseFloat(e.target.value) : undefined }
                              })}
                              className="w-full p-2 rounded border border-slate-300 bg-white"
                              placeholder="e.g. 250000"
                            />
                          </div>

                          <div>
                            <label className="block text-[10px] font-bold text-slate-600 mb-0.5">Gender Restriction</label>
                            <select
                              value={editForm.simple_fields.gender || "ANY"}
                              onChange={(e) => setEditForm({
                                ...editForm,
                                simple_fields: { ...editForm.simple_fields, gender: e.target.value }
                              })}
                              className="w-full p-2 rounded border border-slate-300 bg-white"
                            >
                              <option value="ANY">ANY (No Gender Restriction)</option>
                              <option value="FEMALE">FEMALE ONLY</option>
                              <option value="MALE">MALE ONLY</option>
                            </select>
                          </div>
                        </div>
                      </div>

                      {/* Explicit Condition Clauses */}
                      <div className="space-y-3">
                        <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                          <div>
                            <h4 className="font-bold text-slate-900">Extracted Deterministic Rules & Conditions</h4>
                            <p className="text-[11px] text-slate-500">Atomic conditions evaluated during citizen voice dialogue.</p>
                          </div>
                          <button
                            type="button"
                            onClick={addCondition}
                            className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-xs"
                          >
                            + Add Condition
                          </button>
                        </div>

                        {editForm.conditions.length === 0 ? (
                          <div className="p-6 text-center text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-300">
                            No discrete rule conditions attached.
                          </div>
                        ) : (
                          <div className="space-y-2.5">
                            {editForm.conditions.map((c, idx) => (
                              <div key={idx} className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex flex-col sm:flex-row items-start sm:items-center gap-3">
                                <span className="font-mono text-[10px] text-slate-400 px-1.5 py-0.5 rounded bg-slate-200">{c.condition_id || `COND-${idx + 1}`}</span>
                                <input
                                  type="text"
                                  value={c.field || ""}
                                  onChange={(e) => {
                                    const updated = [...editForm.conditions];
                                    updated[idx].field = e.target.value;
                                    setEditForm({ ...editForm, conditions: updated });
                                  }}
                                  className="w-36 p-1.5 rounded border border-slate-300 bg-white text-[11px]"
                                  placeholder="field (e.g. age)"
                                />
                                <select
                                  value={c.operator || "EQ"}
                                  onChange={(e) => {
                                    const updated = [...editForm.conditions];
                                    updated[idx].operator = e.target.value;
                                    setEditForm({ ...editForm, conditions: updated });
                                  }}
                                  className="w-24 p-1.5 rounded border border-slate-300 bg-white text-[11px]"
                                >
                                  <option value="EQ">EQ (=)</option>
                                  <option value="GTE">GTE (&gt;=)</option>
                                  <option value="LTE">LTE (&lt;=)</option>
                                  <option value="GT">GT (&gt;)</option>
                                  <option value="LT">LT (&lt;)</option>
                                  <option value="NE">NE (!=)</option>
                                  <option value="IN">IN</option>
                                </select>
                                <input
                                  type="text"
                                  value={typeof c.value === "object" ? JSON.stringify(c.value) : (c.value ?? "")}
                                  onChange={(e) => {
                                    const updated = [...editForm.conditions];
                                    updated[idx].value = e.target.value;
                                    setEditForm({ ...editForm, conditions: updated });
                                  }}
                                  className="w-28 p-1.5 rounded border border-slate-300 bg-white text-[11px]"
                                  placeholder="value"
                                />
                                <input
                                  type="text"
                                  value={c.raw_text || ""}
                                  onChange={(e) => {
                                    const updated = [...editForm.conditions];
                                    updated[idx].raw_text = e.target.value;
                                    setEditForm({ ...editForm, conditions: updated });
                                  }}
                                  className="flex-1 p-1.5 rounded border border-slate-300 bg-white text-[11px]"
                                  placeholder="Raw legal clause text..."
                                />
                                <button
                                  type="button"
                                  onClick={() => removeCondition(idx)}
                                  className="text-rose-600 hover:text-rose-800 font-bold px-2 py-1"
                                >
                                  ✕
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* TAB 4: REQUIRED DOCUMENTS */}
                  {activeTab === "documents" && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                        <div>
                          <h3 className="font-bold text-slate-900">Required Documents & Verification Proofs</h3>
                          <p className="text-[11px] text-slate-500">Checklist of certificates, Jan Aadhaar, land records, or ID proofs needed to apply.</p>
                        </div>
                        <button
                          type="button"
                          onClick={addDocument}
                          className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-xs"
                        >
                          + Add Document
                        </button>
                      </div>

                      {editForm.required_documents.length === 0 ? (
                        <div className="p-8 text-center text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-300">
                          No required documents configured.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {editForm.required_documents.map((d, idx) => (
                            <div key={idx} className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 flex flex-col sm:flex-row items-start sm:items-center gap-3">
                              <select
                                value={d.document_type || "OTHER"}
                                onChange={(e) => {
                                  const updated = [...editForm.required_documents];
                                  updated[idx].document_type = e.target.value;
                                  setEditForm({ ...editForm, required_documents: updated });
                                }}
                                className="p-2 rounded border border-slate-300 bg-white font-mono text-[11px]"
                              >
                                <option value="JAN_AADHAAR">JAN_AADHAAR</option>
                                <option value="AADHAAR">AADHAAR</option>
                                <option value="INCOME_CERTIFICATE">INCOME_CERTIFICATE</option>
                                <option value="DOMICILE_CERTIFICATE">DOMICILE_CERTIFICATE</option>
                                <option value="CASTE_CERTIFICATE">CASTE_CERTIFICATE</option>
                                <option value="LAND_RECORD">LAND_RECORD (Jamabandi)</option>
                                <option value="BANK_PASSBOOK">BANK_PASSBOOK</option>
                                <option value="DISABILITY_CERTIFICATE">DISABILITY_CERTIFICATE</option>
                                <option value="RATION_CARD">RATION_CARD</option>
                                <option value="OTHER">OTHER</option>
                              </select>

                              <input
                                type="text"
                                value={d.name_raw || ""}
                                onChange={(e) => {
                                  const updated = [...editForm.required_documents];
                                  updated[idx].name_raw = e.target.value;
                                  setEditForm({ ...editForm, required_documents: updated });
                                }}
                                className="flex-1 p-2 rounded border border-slate-300 bg-white"
                                placeholder="Verbatim document name (e.g. जन आधार कार्ड / मूल निवास प्रमाण पत्र)"
                              />

                              <label className="flex items-center gap-1.5 cursor-pointer select-none whitespace-nowrap">
                                <input
                                  type="checkbox"
                                  checked={Boolean(d.mandatory)}
                                  onChange={(e) => {
                                    const updated = [...editForm.required_documents];
                                    updated[idx].mandatory = e.target.checked;
                                    setEditForm({ ...editForm, required_documents: updated });
                                  }}
                                  className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4"
                                />
                                <span className="text-[11px] font-bold text-slate-700">Mandatory</span>
                              </label>

                              <input
                                type="text"
                                value={d.notes || ""}
                                onChange={(e) => {
                                  const updated = [...editForm.required_documents];
                                  updated[idx].notes = e.target.value;
                                  setEditForm({ ...editForm, required_documents: updated });
                                }}
                                className="w-48 p-2 rounded border border-slate-300 bg-white text-[11px]"
                                placeholder="Issuing authority notes..."
                              />

                              <button
                                type="button"
                                onClick={() => removeDocument(idx)}
                                className="text-rose-600 hover:text-rose-800 font-bold px-2 py-1"
                              >
                                ✕
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB 5: APPLICATION PROCESS */}
                  {activeTab === "application" && (
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Official Portal URL</label>
                          <input
                            type="url"
                            value={editForm.portal_url}
                            onChange={(e) => setEditForm({ ...editForm, portal_url: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs font-mono"
                            placeholder="https://sso.rajasthan.gov.in"
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Responsible Office / Officer</label>
                          <input
                            type="text"
                            value={editForm.office}
                            onChange={(e) => setEditForm({ ...editForm, office: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs"
                            placeholder="e.g. District Social Justice Officer / Gram Panchayat"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Application Fees</label>
                          <input
                            type="text"
                            value={editForm.fees}
                            onChange={(e) => setEditForm({ ...editForm, fees: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs"
                            placeholder="e.g. Free of cost / e-Mitra charges apply"
                          />
                        </div>

                        <div>
                          <label className="block font-bold text-slate-700 mb-1">Application Window / Timeline</label>
                          <input
                            type="text"
                            value={editForm.application_window}
                            onChange={(e) => setEditForm({ ...editForm, application_window: e.target.value })}
                            className="w-full p-2.5 rounded border border-slate-300 text-xs"
                            placeholder="e.g. Open throughout the financial year"
                          />
                        </div>
                      </div>

                      <div className="space-y-3">
                        <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                          <h4 className="font-bold text-slate-900">Step-by-Step Citizen Guidance Steps</h4>
                          <button
                            type="button"
                            onClick={addApplicationStep}
                            className="px-2.5 py-1 rounded bg-slate-200 hover:bg-slate-300 text-slate-800 font-semibold"
                          >
                            + Add Step
                          </button>
                        </div>

                        {editForm.application_steps.length === 0 ? (
                          <div className="p-4 text-center text-slate-400 bg-slate-50 rounded border border-dashed border-slate-300">
                            No sequential steps configured.
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {editForm.application_steps.map((st, idx) => (
                              <div key={idx} className="flex items-center gap-2">
                                <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 font-bold flex items-center justify-center text-[10px]">
                                  {idx + 1}
                                </span>
                                <input
                                  type="text"
                                  value={st}
                                  onChange={(e) => {
                                    const updated = [...editForm.application_steps];
                                    updated[idx] = e.target.value;
                                    setEditForm({ ...editForm, application_steps: updated });
                                  }}
                                  className="flex-1 p-2 rounded border border-slate-300"
                                />
                                <button
                                  type="button"
                                  onClick={() => removeApplicationStep(idx)}
                                  className="text-rose-600 hover:text-rose-800 font-bold px-1.5"
                                >
                                  ✕
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* TAB 6: PDF EXTRACTION EVIDENCE */}
                  {activeTab === "evidence" && (
                    <div className="space-y-4">
                      <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-2">
                        <div className="font-bold text-slate-800 text-xs">PDF Document Provenance</div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-slate-600 font-mono text-[11px]">
                          <div>Source File: <span className="font-bold text-slate-900">{schemeDetail?.source_filename || "Official Circular PDF"}</span></div>
                          <div>Document UUID: <span className="font-bold text-slate-900">{schemeDetail?.source_document_id || "N/A"}</span></div>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <h4 className="font-bold text-slate-900">Verbatim Extracted Evidence Snippets</h4>
                        {(!schemeDetail?.canonical_data?.evidence_registry || schemeDetail.canonical_data.evidence_registry.length === 0) ? (
                          <div className="p-6 text-center text-slate-400 bg-slate-50 rounded-lg border border-dashed border-slate-300">
                            No granular snippet markers preserved for this scheme version.
                          </div>
                        ) : (
                          <div className="space-y-2.5">
                            {schemeDetail.canonical_data.evidence_registry.map((ev, idx) => (
                              <div key={idx} className="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-1">
                                <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                                  <span>ID: {ev.evidence_id}</span>
                                  {ev.page_numbers && ev.page_numbers.length > 0 && (
                                    <span>Page {ev.page_numbers.join(", ")}</span>
                                  )}
                                </div>
                                <div className="text-slate-800 font-serif italic text-xs leading-relaxed">
                                  &quot;{ev.text}&quot;
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Modal Sticky Footer */}
            <div className="px-6 py-3.5 bg-slate-100 border-t border-slate-200 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setSelectedSchemeId(null)}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-200 font-semibold transition"
              >
                Close Without Saving
              </button>

              <button
                type="button"
                onClick={handleSaveScheme}
                disabled={isSaving}
                className="px-6 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold transition shadow-sm flex items-center gap-2"
              >
                {isSaving ? (
                  <>
                    <span className="animate-spin text-sm">↻</span>
                    <span>Saving to Database...</span>
                  </>
                ) : (
                  <>
                    <span>💾</span>
                    <span>Save Changes to Database</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
