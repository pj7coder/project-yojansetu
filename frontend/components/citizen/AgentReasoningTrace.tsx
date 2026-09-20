"use client";

import React, { useState } from "react";
import { ToolExecutionStep, SchemeCitation } from "@/types/agent";

interface AgentReasoningTraceProps {
  language: "hi" | "en";
  steps: ToolExecutionStep[];
  executionTimeMs: number;
  citations?: SchemeCitation[];
  onCitationClick?: (citation: SchemeCitation) => void;
}

export function AgentReasoningTrace({
  language,
  steps,
  executionTimeMs,
  citations = [],
  onCitationClick,
}: AgentReasoningTraceProps) {
  const isHi = language === "hi";
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [expandedStepIndex, setExpandedStepIndex] = useState<number | null>(null);

  if (!steps || steps.length === 0) {
    return null;
  }

  const toggleStep = (idx: number) => {
    setExpandedStepIndex(expandedStepIndex === idx ? null : idx);
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden my-4">
      {/* Top Banner */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-4 py-3 bg-linear-to-r from-slate-900 via-slate-800 to-indigo-950 text-white flex items-center justify-between cursor-pointer hover:bg-slate-800 transition-colors select-none"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400" />
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-black uppercase tracking-wider text-emerald-400 font-mono">
                {isHi ? "AI एजेंट रीज़निंग ट्रेस (ReAct)" : "Agent Reasoning Trace (ReAct)"}
              </span>
              <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full border border-slate-700">
                {steps.length} {isHi ? "चरण" : "Steps"}
              </span>
            </div>
            <div className="text-xs text-slate-300">
              {isHi
                ? "प्रत्येक निष्कर्ष आधिकारिक राजपत्रित परिपत्र और शून्य-भ्रांति नियमों पर आधारित है"
                : "Multi-step tool execution with deterministic AST validation & Gazetted citations"}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden sm:inline-block text-[11px] font-mono text-emerald-400 bg-emerald-950/80 px-2.5 py-1 rounded border border-emerald-800">
            ⚡ {executionTimeMs}ms
          </span>
          <span className="text-slate-400 text-sm font-bold">
            {isExpanded ? "▲" : "▼"}
          </span>
        </div>
      </div>

      {/* Accordion Content */}
      {isExpanded && (
        <div className="p-4 sm:p-5 space-y-3 bg-slate-50/50">
          {steps.map((step, idx) => {
            const isStepExpanded = expandedStepIndex === idx;
            return (
              <div
                key={idx}
                className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs hover:border-slate-300 transition-all"
              >
                {/* Step Header */}
                <div
                  onClick={() => toggleStep(idx)}
                  className="p-3.5 flex items-start justify-between gap-3 cursor-pointer select-none bg-white hover:bg-slate-50"
                >
                  <div className="flex items-start gap-2.5">
                    <span className="w-6 h-6 rounded-full bg-orange-100 text-orange-800 font-extrabold text-xs flex items-center justify-center shrink-0 mt-0.5">
                      {step.step}
                    </span>
                    <div>
                      <div className="text-xs font-bold text-slate-800 leading-snug">
                        {step.thought}
                      </div>
                      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                        <span className="inline-flex items-center gap-1 font-mono text-[11px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded font-semibold border border-indigo-200/60">
                          ⚙️ {step.tool_name}
                        </span>
                        {step.duration_ms > 0 && (
                          <span className="text-[10px] text-slate-400 font-mono">
                            {step.duration_ms}ms
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <span className="text-xs text-slate-400 font-mono shrink-0">
                    {isStepExpanded ? "Hide Details ▲" : "Inspect Tool Details ▼"}
                  </span>
                </div>

                {/* Expanded Details: Tool Input & Output */}
                {isStepExpanded && (
                  <div className="p-3.5 bg-slate-900 text-slate-100 text-[11px] font-mono border-t border-slate-200 space-y-3">
                    <div>
                      <div className="text-emerald-400 font-bold mb-1 flex items-center gap-1">
                        <span>▶</span> Tool Parameters (Input)
                      </div>
                      <pre className="bg-slate-950 p-2.5 rounded-lg overflow-x-auto text-slate-300 text-[10px]">
                        {JSON.stringify(step.tool_args, null, 2)}
                      </pre>
                    </div>

                    <div>
                      <div className="text-amber-400 font-bold mb-1 flex items-center gap-1">
                        <span>◀</span> Tool Observation (Deterministic Output)
                      </div>
                      <pre className="bg-slate-950 p-2.5 rounded-lg overflow-x-auto text-amber-200 text-[10px] max-h-48">
                        {JSON.stringify(step.tool_result, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Citations Ribbon */}
          {citations && citations.length > 0 && (
            <div className="mt-4 pt-3 border-t border-slate-200">
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                  <span>📜</span>
                  <span>
                    {isHi
                      ? "सत्यापित राजपत्रित साक्ष्य एवं परिपत्र (Grounded Citations)"
                      : "Verified Gazetted Circular Citations"}
                  </span>
                </span>
                <span className="text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded">
                  {isHi ? "100% प्रामाणिक" : "Zero Hallucination"}
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                {citations.map((cit, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => onCitationClick && onCitationClick(cit)}
                    className="inline-flex items-center gap-1.5 text-xs font-mono font-bold bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 px-3 py-1 rounded-lg transition-colors cursor-pointer"
                    title={cit.snippet}
                  >
                    <span>📑</span>
                    <span>{cit.citation_tag}</span>
                    <span className="text-[10px] text-amber-600">→</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default AgentReasoningTrace;
