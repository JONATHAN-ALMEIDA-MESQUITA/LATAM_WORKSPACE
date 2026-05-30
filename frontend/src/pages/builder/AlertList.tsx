/**
 * AlertList - lista de alertas (Phase 5).
 *
 * Cards com badges (tipo, severidade, enabled, ultima avaliacao).
 * Acoes inline: toggle enabled, test, evaluate now, edit, delete.
 * Botao "Evaluate all" para batch.
 */

import { useEffect, useState } from "react";
import { AlertsAPI } from "@/api/client";
import { AlertBuilder } from "@/components/alert/AlertBuilder";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAuthStore } from "@/store/authStore";
import type { Alert, AlertSeverity, AlertType } from "@/types";

const TYPE_LABEL: Record<AlertType, string> = {
  metric_threshold: "Metric Threshold",
  metric_change: "Metric Change",
  forecast_quality: "Forecast Quality",
  pipeline_failure: "Pipeline Failure",
  dashboard_stale: "Dashboard Stale",
};

const TYPE_TONE: Record<AlertType, "neutral" | "info" | "warning" | "success" | "danger"> = {
  metric_threshold: "info",
  metric_change: "info",
  forecast_quality: "info",
  pipeline_failure: "danger",
  dashboard_stale: "neutral",
};

const SEVERITY_TONE: Record<AlertSeverity, "neutral" | "info" | "warning" | "danger"> = {
  info: "info",
  warning: "warning",
  critical: "danger",
};

const EVAL_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  fired: "danger",
  ok: "success",
  error: "warning",
  cooldown: "neutral",
  disabled: "neutral",
  would_fire: "warning",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function AlertList() {
  const permissions = useAuthStore((s) => s.permissions);
  const accessibleWorkspaces = useAuthStore((s) => s.menu?.workspaces ?? []);
  const canCreate = !!permissions?.create_alert;

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [fWorkspace, setFWorkspace] = useState("");
  const [fType, setFType] = useState("");
  const [fSeverity, setFSeverity] = useState("");
  const [fEnabled, setFEnabled] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const [builderOpen, setBuilderOpen] = useState(false);
  const [editing, setEditing] = useState<Alert | null>(null);
  const [evaluating, setEvaluating] = useState<number | null>(null);
  const [batchRunning, setBatchRunning] = useState(false);
  const [lastBatch, setLastBatch] = useState<{
    evaluated: number;
    fired: number;
    errors: number;
    cooldowned: number;
  } | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const items = await AlertsAPI.list({
        workspace: fWorkspace || undefined,
        alert_type: fType || undefined,
        severity: fSeverity || undefined,
        enabled:
          fEnabled === "true" ? true : fEnabled === "false" ? false : undefined,
      });
      setAlerts(items);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar alertas.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fWorkspace, fType, fSeverity, fEnabled]);

  async function handleToggle(a: Alert) {
    try {
      await AlertsAPI.toggle(a.id);
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    }
  }

  async function handleEvaluate(a: Alert) {
    setEvaluating(a.id);
    try {
      const r = await AlertsAPI.evaluate(a.id);
      alert(
        `Status: ${r.status.toUpperCase()}\n\n${r.title}\n\n${r.message}` +
          (r.error ? `\n\nERRO: ${r.error}` : ""),
      );
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    } finally {
      setEvaluating(null);
    }
  }

  async function handleTest(a: Alert) {
    setEvaluating(a.id);
    try {
      const r = await AlertsAPI.test(a.id);
      alert(
        `[TESTE - nao notifica] Status: ${r.status.toUpperCase()}\n\n${r.title}\n\n${r.message}` +
          (r.error ? `\n\nERRO: ${r.error}` : ""),
      );
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    } finally {
      setEvaluating(null);
    }
  }

  async function handleEvaluateAll() {
    setBatchRunning(true);
    setLastBatch(null);
    try {
      const r = await AlertsAPI.evaluateAll(fWorkspace || undefined);
      setLastBatch({
        evaluated: r.evaluated,
        fired: r.fired,
        errors: r.errors,
        cooldowned: r.cooldowned,
      });
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    } finally {
      setBatchRunning(false);
    }
  }

  async function handleDelete(a: Alert) {
    if (!confirm(`Remover alerta "${a.name}"?`)) return;
    try {
      await AlertsAPI.delete(a.id);
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    }
  }

  function openCreate() {
    setEditing(null);
    setBuilderOpen(true);
  }

  function openEdit(a: Alert) {
    setEditing(a);
    setBuilderOpen(true);
  }

  return (
    <PageContainer
      title="Alerts"
      subtitle="Regras de monitoramento sobre metricas, forecasts, pipelines e dashboards. Disparam in-app + e-mail (mock) e fazem trigger automatico apos runs."
      actions={
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleEvaluateAll}
            disabled={batchRunning}
          >
            {batchRunning ? "Avaliando..." : "Evaluate all"}
          </Button>
          {canCreate && (
            <Button onClick={openCreate} variant="primary" size="sm">
              + Novo alerta
            </Button>
          )}
        </div>
      }
    >
      <Card className="mb-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          <div>
            <label className="text-xs font-semibold text-slate-600">Workspace</label>
            <select
              className="input"
              value={fWorkspace}
              onChange={(e) => setFWorkspace(e.target.value)}
            >
              <option value="">Todos</option>
              {accessibleWorkspaces.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
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
            <label className="text-xs font-semibold text-slate-600">Estado</label>
            <select
              className="input"
              value={fEnabled}
              onChange={(e) => setFEnabled(e.target.value)}
            >
              <option value="">Todos</option>
              <option value="true">Habilitados</option>
              <option value="false">Desabilitados</option>
            </select>
          </div>
          <div className="flex items-end text-xs text-slate-500">
            {alerts.length} alerta(s)
          </div>
        </div>
      </Card>

      {error && (
        <Card className="mb-3 border-rose-200 bg-rose-50 text-sm text-rose-700">{error}</Card>
      )}

      {lastBatch && (
        <Card className="mb-3 border-brand-200 bg-brand-50 text-xs">
          <div>
            <strong>Batch executado:</strong> avaliados={lastBatch.evaluated} · disparados=
            <span className="text-rose-700 font-semibold">{lastBatch.fired}</span> · erros=
            {lastBatch.errors} · em cooldown={lastBatch.cooldowned}
          </div>
        </Card>
      )}

      {loading ? (
        <Card className="text-sm text-slate-500">Carregando alertas...</Card>
      ) : alerts.length === 0 ? (
        <EmptyState
          title="Nenhum alerta encontrado"
          description="Crie alertas para ser notificado quando metricas/forecasts/pipelines/dashboards saem do esperado."
        />
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => (
            <Card key={a.id} className={!a.enabled ? "opacity-60" : ""}>
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="text-base font-semibold text-brand-700 hover:underline"
                      onClick={() => openEdit(a)}
                    >
                      {a.name}
                    </button>
                    <Badge tone={SEVERITY_TONE[a.severity] ?? "neutral"}>
                      {a.severity}
                    </Badge>
                    <Badge tone={TYPE_TONE[a.alert_type] ?? "neutral"}>
                      {TYPE_LABEL[a.alert_type] ?? a.alert_type}
                    </Badge>
                    {a.enabled ? (
                      <Badge tone="success">ENABLED</Badge>
                    ) : (
                      <Badge tone="neutral">DISABLED</Badge>
                    )}
                    {a.last_eval_status && (
                      <Badge tone={EVAL_TONE[a.last_eval_status] ?? "neutral"}>
                        last: {a.last_eval_status}
                      </Badge>
                    )}
                    {a.fire_count > 0 && (
                      <Badge tone="warning">{a.fire_count}x disparado</Badge>
                    )}
                  </div>
                  {a.description && (
                    <div className="mt-1 text-xs text-slate-600">{a.description}</div>
                  )}
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
                    <span>workspace: {a.workspace}</span>
                    {a.business_area && <span>area: {a.business_area}</span>}
                    <span>
                      target: {a.target_kind} #{a.target_id}
                    </span>
                    <span>cooldown: {a.cooldown_minutes}min</span>
                    <span>canais: {(a.channels ?? []).join(", ")}</span>
                    <span>ultima eval: {fmtDate(a.last_evaluated_at)}</span>
                    {a.last_fired_at && <span>ultimo disparo: {fmtDate(a.last_fired_at)}</span>}
                    {a.last_eval_error && (
                      <span className="text-rose-600">erro: {a.last_eval_error}</span>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => handleTest(a)}
                    disabled={evaluating === a.id}
                  >
                    Testar
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => handleEvaluate(a)}
                    disabled={evaluating === a.id || !a.enabled}
                  >
                    {evaluating === a.id ? "..." : "Evaluate now"}
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => handleToggle(a)}>
                    {a.enabled ? "Desabilitar" : "Habilitar"}
                  </Button>
                  {canCreate && (
                    <Button size="sm" variant="danger" onClick={() => handleDelete(a)}>
                      Remover
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <AlertBuilder
        open={builderOpen}
        onClose={() => setBuilderOpen(false)}
        onSaved={() => {
          setBuilderOpen(false);
          refresh();
        }}
        initialAlert={editing}
        defaultWorkspace={accessibleWorkspaces[0] ?? "LATAM"}
      />
    </PageContainer>
  );
}
