/**
 * NotificationBell - badge no header com inbox dropdown.
 *
 * - Faz polling a cada 30s pra atualizar o summary.
 * - Mostra contador de notifications nao-acknowledged.
 * - Dropdown com ultimas 5 notifications + link "Ver todas" -> /notifications
 * - Botoes inline pra mark-read e ack.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { NotificationsAPI } from "@/api/client";
import { useAuthStore } from "@/store/authStore";
import type { Notification, NotificationSummary } from "@/types";

const POLL_INTERVAL_MS = 30_000;

const SEVERITY_DOT: Record<string, string> = {
  info: "bg-sky-500",
  warning: "bg-amber-500",
  critical: "bg-rose-600",
};

const SEVERITY_BG: Record<string, string> = {
  info: "bg-sky-50 border-sky-200",
  warning: "bg-amber-50 border-amber-200",
  critical: "bg-rose-50 border-rose-200",
};

function fmtRelative(iso: string): string {
  try {
    const d = new Date(iso);
    const diff = Date.now() - d.getTime();
    const min = Math.floor(diff / 60_000);
    if (min < 1) return "agora";
    if (min < 60) return `${min}m atras`;
    const hours = Math.floor(min / 60);
    if (hours < 24) return `${hours}h atras`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d atras`;
    return d.toLocaleDateString();
  } catch {
    return iso;
  }
}

export function NotificationBell() {
  const navigate = useNavigate();
  const permissions = useAuthStore((s) => s.permissions);
  const canView = !!permissions?.view_alerts;

  const [summary, setSummary] = useState<NotificationSummary | null>(null);
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    if (!canView) return;
    try {
      const s = await NotificationsAPI.summary();
      setSummary(s);
    } catch {
      // silent - pode acontecer logo apos login antes do token estar ativo
    }
  }, [canView]);

  useEffect(() => {
    refresh();
    if (!canView) return;
    const id = window.setInterval(refresh, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [refresh, canView]);

  // Fecha dropdown ao clicar fora
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const unread = summary?.total_unread ?? 0;
  const unack = summary?.total_unack ?? 0;
  const recent = summary?.recent ?? [];

  const dotClass = useMemo(() => {
    if (!summary) return "bg-slate-400";
    if (summary.by_severity.critical > 0) return SEVERITY_DOT.critical;
    if (summary.by_severity.warning > 0) return SEVERITY_DOT.warning;
    if (summary.by_severity.info > 0) return SEVERITY_DOT.info;
    return "bg-slate-400";
  }, [summary]);

  if (!canView) return null;

  async function handleMarkRead(n: Notification) {
    try {
      await NotificationsAPI.markRead(n.id);
      await refresh();
    } catch {
      /* noop */
    }
  }

  async function handleAck(n: Notification) {
    try {
      await NotificationsAPI.acknowledge(n.id, "");
      await refresh();
    } catch {
      /* noop */
    }
  }

  async function handleReadAll() {
    try {
      await NotificationsAPI.markAllRead();
      await refresh();
    } catch {
      /* noop */
    }
  }

  function handleOpenAll() {
    setOpen(false);
    navigate("/notifications");
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-700 transition hover:bg-slate-200"
        aria-label="Notificacoes"
        title={`${unack} notificacoes pendentes (${unread} nao lidas)`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-5 w-5"
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {unack > 0 && (
          <span
            className={`absolute -top-0.5 -right-0.5 flex h-5 min-w-[1.25rem] items-center justify-center rounded-full ${dotClass} px-1 text-[10px] font-bold text-white ring-2 ring-white`}
          >
            {unack > 99 ? "99+" : unack}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-96 max-w-[90vw] origin-top-right rounded-lg border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
            <div className="text-sm font-semibold text-slate-700">
              Notificacoes
              {summary && (
                <span className="ml-2 text-xs font-normal text-slate-500">
                  {summary.total_unread} nao lidas · {summary.total_unack} pendentes
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={handleReadAll}
              className="text-[11px] text-brand-700 hover:underline"
              disabled={unread === 0}
            >
              Marcar todas como lidas
            </button>
          </div>

          {summary && (
            <div className="flex gap-2 border-b border-slate-200 px-4 py-2 text-[11px]">
              <span className="flex items-center gap-1">
                <span className={`inline-block h-2 w-2 rounded-full ${SEVERITY_DOT.critical}`} />
                Critical: <strong>{summary.by_severity.critical}</strong>
              </span>
              <span className="flex items-center gap-1">
                <span className={`inline-block h-2 w-2 rounded-full ${SEVERITY_DOT.warning}`} />
                Warning: <strong>{summary.by_severity.warning}</strong>
              </span>
              <span className="flex items-center gap-1">
                <span className={`inline-block h-2 w-2 rounded-full ${SEVERITY_DOT.info}`} />
                Info: <strong>{summary.by_severity.info}</strong>
              </span>
            </div>
          )}

          <div className="max-h-80 overflow-auto">
            {recent.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-slate-500">
                Sem notificacoes recentes.
              </div>
            ) : (
              recent.map((n) => (
                <div
                  key={n.id}
                  className={`flex items-start gap-2 border-b border-slate-100 px-3 py-2 text-xs ${
                    n.status === "unread" ? "bg-slate-50" : ""
                  }`}
                >
                  <div
                    className={`mt-1 h-2 w-2 shrink-0 rounded-full ${SEVERITY_DOT[n.severity] ?? "bg-slate-400"}`}
                  />
                  <div className="min-w-0 flex-1">
                    <div
                      className={`mb-0.5 flex items-center gap-1 font-semibold ${
                        n.status === "unread" ? "text-slate-900" : "text-slate-600"
                      }`}
                    >
                      <span className="truncate">{n.title}</span>
                    </div>
                    <div className="line-clamp-2 text-slate-600">{n.message}</div>
                    <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
                      <span>{fmtRelative(n.fired_at)}</span>
                      <span>·</span>
                      <span className="font-mono">{n.alert_type}</span>
                      {n.workspace && (
                        <>
                          <span>·</span>
                          <span>{n.workspace}</span>
                        </>
                      )}
                    </div>
                    <div className="mt-1 flex gap-2">
                      {n.status === "unread" && (
                        <button
                          type="button"
                          onClick={() => handleMarkRead(n)}
                          className="text-[10px] text-brand-700 hover:underline"
                        >
                          marcar lida
                        </button>
                      )}
                      {n.status !== "acknowledged" && (
                        <button
                          type="button"
                          onClick={() => handleAck(n)}
                          className="text-[10px] text-emerald-700 hover:underline"
                        >
                          ack
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="border-t border-slate-200 px-4 py-2 text-center">
            <button
              type="button"
              onClick={handleOpenAll}
              className="text-xs font-semibold text-brand-700 hover:underline"
            >
              Ver todas as notificacoes →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
