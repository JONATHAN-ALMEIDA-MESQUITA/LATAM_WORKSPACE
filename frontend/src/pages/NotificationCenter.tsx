/**
 * NotificationCenter - inbox completa de notifications do usuario.
 *
 * Filtros: status, severidade, tipo, workspace.
 * Acoes: mark read individual/all, ack com nota, expand pra ver contexto.
 */

import { useEffect, useState } from "react";
import { NotificationsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type { AlertSeverity, AlertType, Notification, NotificationStatus } from "@/types";

const SEVERITY_TONE: Record<AlertSeverity, "neutral" | "info" | "warning" | "danger"> = {
  info: "info",
  warning: "warning",
  critical: "danger",
};

const SEVERITY_BORDER: Record<AlertSeverity, string> = {
  info: "border-l-sky-500",
  warning: "border-l-amber-500",
  critical: "border-l-rose-600",
};

const STATUS_TONE: Record<NotificationStatus, "neutral" | "info" | "warning" | "success"> = {
  unread: "info",
  read: "neutral",
  acknowledged: "success",
};

const TYPE_LABEL: Record<AlertType, string> = {
  metric_threshold: "Metric Threshold",
  metric_change: "Metric Change",
  forecast_quality: "Forecast Quality",
  pipeline_failure: "Pipeline Failure",
  dashboard_stale: "Dashboard Stale",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function NotificationCenter() {
  const permissions = useAuthStore((s) => s.permissions);
  const canManage = !!permissions?.manage_alerts;

  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [fStatus, setFStatus] = useState("");
  const [fSeverity, setFSeverity] = useState("");
  const [fType, setFType] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  const [ackOpen, setAckOpen] = useState(false);
  const [ackTarget, setAckTarget] = useState<Notification | null>(null);
  const [ackNote, setAckNote] = useState("");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const r = await NotificationsAPI.list({
        status: fStatus || undefined,
        severity: fSeverity || undefined,
        alert_type: fType || undefined,
        limit: 200,
      });
      setItems(r);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar notificacoes.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fStatus, fSeverity, fType]);

  async function handleMarkRead(n: Notification) {
    try {
      await NotificationsAPI.markRead(n.id);
      await refresh();
    } catch {
      /* noop */
    }
  }

  async function handleMarkAllRead() {
    try {
      const r = await NotificationsAPI.markAllRead();
      alert(`${r.updated} notificacao(oes) marcadas como lidas.`);
      await refresh();
    } catch {
      /* noop */
    }
  }

  function openAck(n: Notification) {
    setAckTarget(n);
    setAckNote("");
    setAckOpen(true);
  }

  async function handleAck() {
    if (!ackTarget) return;
    try {
      await NotificationsAPI.acknowledge(ackTarget.id, ackNote);
      setAckOpen(false);
      await refresh();
    } catch {
      /* noop */
    }
  }

  const unreadCount = items.filter((n) => n.status === "unread").length;
  const unackCount = items.filter((n) => n.status !== "acknowledged").length;

  return (
    <PageContainer
      title="Notificacoes"
      subtitle="Inbox de alertas disparados. Use ack para marcar como tratado (com nota opcional para audit)."
      actions={
        <Button
          variant="secondary"
          size="sm"
          onClick={handleMarkAllRead}
          disabled={unreadCount === 0}
        >
          Marcar todas como lidas
        </Button>
      }
    >
      <Card className="mb-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div>
            <label className="text-xs font-semibold text-slate-600">Status</label>
            <select className="input" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
              <option value="">Todos</option>
              <option value="unread">Nao lidas</option>
              <option value="read">Lidas</option>
              <option value="acknowledged">Acknowledged</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Severidade</label>
            <select
              className="input"
              value={fSeverity}
              onChange={(e) => setFSeverity(e.target.value)}
            >
              <option value="">Todas</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="critical">Critical</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Tipo</label>
            <select className="input" value={fType} onChange={(e) => setFType(e.target.value)}>
              <option value="">Todos</option>
              {Object.entries(TYPE_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end text-xs text-slate-500">
            {items.length} no total · {unreadCount} nao lidas · {unackCount} pendentes
            {canManage && <span className="ml-2 text-brand-700">(admin: ve todas)</span>}
          </div>
        </div>
      </Card>

      {error && (
        <Card className="mb-3 border-rose-200 bg-rose-50 text-sm text-rose-700">{error}</Card>
      )}

      {loading ? (
        <Card className="text-sm text-slate-500">Carregando notificacoes...</Card>
      ) : items.length === 0 ? (
        <EmptyState
          title="Inbox vazia"
          description="Sem notificacoes para mostrar com esses filtros."
        />
      ) : (
        <div className="space-y-2">
          {items.map((n) => (
            <Card
              key={n.id}
              className={`border-l-4 ${SEVERITY_BORDER[n.severity]} ${
                n.status === "unread" ? "" : "bg-slate-50/50"
              }`}
            >
              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={SEVERITY_TONE[n.severity] ?? "neutral"}>{n.severity}</Badge>
                    <Badge tone={STATUS_TONE[n.status] ?? "neutral"}>{n.status}</Badge>
                    <Badge tone="neutral">{TYPE_LABEL[n.alert_type] ?? n.alert_type}</Badge>
                    <span className="text-[10px] text-slate-500">
                      {fmtDate(n.fired_at)}
                    </span>
                  </div>
                  <div
                    className={`mt-1 ${
                      n.status === "unread" ? "font-semibold text-slate-900" : "text-slate-700"
                    }`}
                  >
                    {n.title}
                  </div>
                  <div className="text-xs text-slate-600">{n.message}</div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500">
                    <span>alerta: {n.alert_name}</span>
                    <span>destinatario: {n.recipient_email}</span>
                    <span>workspace: {n.workspace}</span>
                    {n.business_area && <span>area: {n.business_area}</span>}
                    {n.acknowledged_by && (
                      <span>ack por: {n.acknowledged_by} ({fmtDate(n.acknowledged_at)})</span>
                    )}
                    {n.ack_note && <span>nota: "{n.ack_note}"</span>}
                  </div>
                  {expanded === n.id && (
                    <div className="mt-2 rounded border border-slate-200 bg-white p-2 text-[11px]">
                      <div className="mb-1 font-semibold text-slate-700">Contexto:</div>
                      <pre className="overflow-auto text-[10px] leading-tight">
                        {JSON.stringify(n.context, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setExpanded(expanded === n.id ? null : n.id)}
                  >
                    {expanded === n.id ? "Ocultar" : "Contexto"}
                  </Button>
                  {n.status === "unread" && (
                    <Button size="sm" variant="secondary" onClick={() => handleMarkRead(n)}>
                      Marcar lida
                    </Button>
                  )}
                  {n.status !== "acknowledged" && (
                    <Button size="sm" variant="primary" onClick={() => openAck(n)}>
                      Acknowledge
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={ackOpen}
        title={ackTarget ? `Acknowledge: ${ackTarget.title}` : "Acknowledge"}
        onClose={() => setAckOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAckOpen(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={handleAck}>
              Confirmar ack
            </Button>
          </>
        }
      >
        <div className="space-y-2 text-xs">
          {ackTarget && (
            <div className="rounded bg-slate-50 p-2 text-slate-600">
              <div>{ackTarget.message}</div>
            </div>
          )}
          <div>
            <label className="font-semibold text-slate-600">Nota (opcional)</label>
            <textarea
              className="input min-h-[80px]"
              value={ackNote}
              onChange={(e) => setAckNote(e.target.value)}
              placeholder="Ex: investigado, falso positivo, acao tomada..."
            />
          </div>
        </div>
      </Modal>
    </PageContainer>
  );
}
