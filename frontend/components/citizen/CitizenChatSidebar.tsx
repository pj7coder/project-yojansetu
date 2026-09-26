"use client";

import React, { useState } from "react";

export interface ChatSessionMeta {
  id: string;
  title: string;
  timestamp: number;
  messageCount: number;
  lastMessage?: string;
}

interface CitizenChatSidebarProps {
  sessions: ChatSessionMeta[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  lang: "hi" | "en";
  isOpen?: boolean;
  onClose?: () => void;
}

export function CitizenChatSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  lang = "hi",
  isOpen = true,
  onClose,
}: CitizenChatSidebarProps) {
  const [filterText, setFilterText] = useState("");
  const isHi = lang === "hi";

  const filteredSessions = sessions.filter((s) =>
    s.title.toLowerCase().includes(filterText.toLowerCase()) ||
    (s.lastMessage && s.lastMessage.toLowerCase().includes(filterText.toLowerCase()))
  );

  const formatRelativeTime = (timeMs: number) => {
    const diffSec = Math.floor((Date.now() - timeMs) / 1000);
    if (diffSec < 60) return isHi ? "अभी-अभी" : "Just now";
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)} ${isHi ? "मिनट पहले" : "m ago"}`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} ${isHi ? "घंटे पहले" : "h ago"}`;
    const days = Math.floor(diffSec / 86400);
    return `${days} ${isHi ? "दिन पहले" : "d ago"}`;
  };

  return (
    <aside
      className={`h-full flex flex-col bg-slate-900 text-slate-100 border-r border-slate-800 transition-all duration-200 z-20 ${
        isOpen ? "w-72 sm:w-80 flex-shrink-0" : "hidden"
      }`}
    >
      {/* Top Banner / New Chat CTA */}
      <div className="p-3 border-b border-slate-800 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-orange-500 animate-pulse" />
            <h2 className="text-xs font-black uppercase tracking-wider text-slate-300">
              {isHi ? "पिछली बातचीत" : "Past Chats"}
            </h2>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="lg:hidden p-1 rounded hover:bg-slate-800 text-slate-400 text-sm"
              title="Close history"
            >
              ✕
            </button>
          )}
        </div>

        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl bg-orange-600 hover:bg-orange-500 active:scale-98 text-white font-bold text-xs shadow-md transition-all cursor-pointer"
        >
          <span className="text-base leading-none">+</span>
          <span>{isHi ? "नया चैट शुरू करें" : "New Conversation"}</span>
        </button>

        {/* Filter input if multiple chats */}
        {sessions.length > 3 && (
          <div className="relative">
            <input
              type="text"
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              placeholder={isHi ? "चैट खोजें..." : "Search chats..."}
              className="w-full py-1.5 px-2.5 rounded-lg bg-slate-800/80 border border-slate-700 text-slate-200 placeholder-slate-500 text-xs focus:outline-none focus:border-orange-500"
            />
            {filterText && (
              <button
                onClick={() => setFilterText("")}
                className="absolute right-2 top-1.5 text-xs text-slate-400 hover:text-white"
              >
                ✕
              </button>
            )}
          </div>
        )}
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin scrollbar-thumb-slate-700">
        {filteredSessions.length === 0 ? (
          <div className="py-12 px-4 text-center text-slate-500 space-y-2">
            <div className="text-2xl opacity-60">💬</div>
            <p className="text-xs font-medium">
              {isHi ? "अभी कोई बातचीत सहेजी नहीं गई है" : "No saved chats yet"}
            </p>
            <p className="text-[11px] text-slate-600">
              {isHi
                ? "नीचे किसी भी योजना के बारे में पूछें, वह यहाँ स्वतः सहेज ली जाएगी।"
                : "Ask any scheme question to automatically save conversation."}
            </p>
          </div>
        ) : (
          filteredSessions.map((session) => {
            const isActive = session.id === activeSessionId;
            return (
              <div
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className={`group relative flex items-start justify-between p-2.5 rounded-xl cursor-pointer transition-all border ${
                  isActive
                    ? "bg-slate-800 border-orange-500/60 text-white shadow-sm"
                    : "border-transparent text-slate-300 hover:bg-slate-800/50 hover:text-white"
                }`}
              >
                <div className="min-w-0 flex-1 pr-2">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs">💬</span>
                    <h3 className="text-xs font-semibold truncate leading-snug">
                      {session.title || (isHi ? "बातचीत" : "Conversation")}
                    </h3>
                  </div>
                  {session.lastMessage && (
                    <p className="text-[11px] text-slate-400 truncate mt-0.5 pl-4">
                      {session.lastMessage}
                    </p>
                  )}
                  <div className="text-[10px] text-slate-500 mt-1 pl-4 flex items-center gap-2">
                    <span>{formatRelativeTime(session.timestamp)}</span>
                    <span>•</span>
                    <span>
                      {session.messageCount} {isHi ? "संदेश" : "msgs"}
                    </span>
                  </div>
                </div>

                {/* Delete button */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(session.id);
                  }}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-700/60 active:scale-90 transition opacity-80 sm:opacity-0 sm:group-hover:opacity-100 flex-shrink-0 cursor-pointer"
                  title={isHi ? "यह चैट हटाएं" : "Delete conversation"}
                >
                  <span className="text-sm">🗑️</span>
                </button>
              </div>
            );
          })
        )}
      </div>

      {/* Bottom Info / Privacy Badge */}
      <div className="p-3 border-t border-slate-800 text-[11px] text-slate-500 flex items-center justify-between">
        <span className="flex items-center gap-1 text-slate-400">
          <span>🔒</span>
          <span>{isHi ? "स्थानीय व सुरक्षित" : "Local & Private"}</span>
        </span>
        <span className="text-[10px] text-slate-600 font-mono">YS-v5</span>
      </div>
    </aside>
  );
}
