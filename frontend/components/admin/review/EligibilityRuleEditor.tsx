"use client";

import React, { useState } from "react";

export interface RuleCondition {
  field: string;
  operator: "GTE" | "LTE" | "EQ" | "IN" | "NEQ";
  value: any;
  unit?: string;
  currency?: string;
  period?: string;
}

interface EligibilityRuleEditorProps {
  initialCondition?: any;
  onSave: (condition: any, reason: string) => Promise<void>;
  onCancel: () => void;
  isSubmitting: boolean;
}

export function EligibilityRuleEditor({
  initialCondition,
  onSave,
  onCancel,
  isSubmitting,
}: EligibilityRuleEditorProps) {
  const [field, setField] = useState<string>(initialCondition?.field || "age");
  const [operator, setOperator] = useState<"GTE" | "LTE" | "EQ" | "IN" | "NEQ">(
    initialCondition?.operator || "GTE"
  );
  const [value, setValue] = useState<string>(
    initialCondition?.value !== undefined ? String(initialCondition.value) : "60"
  );
  const [unit, setUnit] = useState<string>(initialCondition?.unit || "years");
  const [currency, setCurrency] = useState<string>(initialCondition?.currency || "INR");
  const [period, setPeriod] = useState<string>(initialCondition?.period || "ANNUAL");
  const [reason, setReason] = useState<string>("");

  const handleSave = async () => {
    if (!reason.trim()) return;

    let parsedVal: any = value;
    if (!isNaN(Number(value)) && value.trim() !== "") {
      parsedVal = Number(value);
    } else if (value.toLowerCase() === "true") {
      parsedVal = true;
    } else if (value.toLowerCase() === "false") {
      parsedVal = false;
    }

    const ruleObj: any = {
      field,
      operator,
      value: parsedVal,
    };

    if (field === "age") {
      ruleObj.unit = unit;
    } else if (field.includes("income")) {
      ruleObj.currency = currency;
      ruleObj.period = period;
    }

    await onSave(ruleObj, reason.trim());
  };

  return (
    <div className="bg-white border border-slate-300 rounded-xl p-5 shadow-md space-y-4">
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <h4 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          ⚙ Structured Eligibility Rule Editor
        </h4>
        <span className="text-[11px] text-slate-500">
          Edits canonical condition without manual JSON entry
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
        {/* Field Selection */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Eligibility Field
          </label>
          <select
            value={field}
            onChange={(e) => setField(e.target.value)}
            className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white"
          >
            <option value="age">Age (आयु)</option>
            <option value="family_income">Family Income (पारिवारिक आय)</option>
            <option value="residency">Residency (मूल निवास)</option>
            <option value="bpl_status">BPL Status (बीपीएल)</option>
            <option value="category">Social Category (वर्ग/जाति)</option>
            <option value="gender">Gender (लिंग)</option>
            <option value="disability_percentage">Disability % (दिव्यांगता)</option>
          </select>
        </div>

        {/* Operator */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Comparison Operator
          </label>
          <select
            value={operator}
            onChange={(e) => setOperator(e.target.value as any)}
            className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white font-mono"
          >
            <option value="GTE">&gt;= (Greater Than / Equal)</option>
            <option value="LTE">&lt;= (Less Than / Equal)</option>
            <option value="EQ">== (Equals)</option>
            <option value="IN">IN (One of set)</option>
            <option value="NEQ">!= (Not Equals)</option>
          </select>
        </div>

        {/* Target Value */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1">
            Canonical Target Value
          </label>
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="e.g. 60 or 200000 or Rajasthan"
            className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white"
          />
        </div>

        {/* Unit / Currency Conditional Controls */}
        {field === "age" && (
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Unit
            </label>
            <input
              type="text"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white"
            />
          </div>
        )}

        {field.includes("income") && (
          <>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Currency
              </label>
              <input
                type="text"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Period
              </label>
              <select
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                className="w-full text-xs p-2 rounded-lg border border-slate-300 bg-white"
              >
                <option value="ANNUAL">Annual (वार्षिक)</option>
                <option value="MONTHLY">Monthly (मासिक)</option>
              </select>
            </div>
          </>
        )}
      </div>

      {/* Structured Preview */}
      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs">
        <div className="font-semibold text-slate-600 mb-1">Rule Preview:</div>
        <div className="font-mono text-blue-900 font-bold">
          {field} {operator} {value} {field === "age" ? unit : ""} {field.includes("income") ? `${currency} (${period})` : ""}
        </div>
      </div>

      {/* Mandatory Audit Reason */}
      <div>
        <label className="block text-xs font-semibold text-slate-700 mb-1">
          Mandatory Edit Reason *
        </label>
        <input
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Official audit justification for modifying this condition..."
          className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Buttons */}
      <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={!reason.trim() || isSubmitting}
          className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 shadow-sm"
        >
          Save & Revalidate
        </button>
      </div>
    </div>
  );
}
