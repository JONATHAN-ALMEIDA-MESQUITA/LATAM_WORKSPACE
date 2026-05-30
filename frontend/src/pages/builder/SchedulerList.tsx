/**
 * Scheduler - gestao de jobs agendados (Phase 6).
 *
 * Lista jobs com cron, proxima execucao, status APScheduler.
 * Acoes: Run now, Pause/Resume, historico de runs, criar job.
 */

import { useEffect, useState } from "react";
import {
  ForecastsAPI,
  PipelinesAPI,
  ScheduledJobsAPI,
} from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type {
  ForecastSummary,
  PipelineSummary,
  ScheduledJob,
  ScheduledJobCreatePayload,
  ScheduledJobRun,
  ScheduledJobType,
  SchedulerStatus,
} from "@/types";

const JOB_TYPE_LABELS: Record<ScheduledJobType, string> = {
  pipeline_run: "Pipeline Run",
  forecast_train: "Forecast Train",
  alerts_evaluate: "Alerts Evaluate",
};

const RUN_STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Success: "success",
  Failed: "danger",
  Running: "warning",
  Skipped: "neutral",
};

const CRON_PRESETS: { label: string; value: string }[] = [
  { label: "Diario 06:00 UTC", value: "0 6 * * *" },
  { label: "Diario 05:00 UTC", value: "0 5 * * *" },
  { label: "Segunda 08:00 UTC", value: "0 8 * * 1" },
  { label: "Mensal dia 1, 07:00", value: "0 7 1 * *" },
  { label: "A cada hora", value: "0 * * * *" },
];

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function SchedulerList() {
  const permissions = useAuthStore((s) => s.permissions);
  const workspaces = useAuthStore((s) => s.menu?.workspaces ?? []);
  const canSchedule = !!permissions?.schedule_job;

  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [pipelines, setPipelines] = useState<PipelineSummary[]>([]);
  const [forecasts, setForecasts] = useState<ForecastSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [fWorkspace, setFWorkspace] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyJob, setHistoryJob] = useState<ScheduledJob | null>(null);
  const [runs, setRuns] = useState<ScheduledJobRun[]>([]);
  const [runningId, setRunningId] = useState<number | null>(null);

  const [form, setForm] = useState<ScheduledJobCreatePayload>({
    name: "",
    description: "",
    workspace: workspaces[0] ?? "LATAM",
    business_area: "",
    job_type: "pipeline_run",
    target_id: null,
    cron_expression: "0 6 * * *",
    timezone: "UTC",
    enabled: true,
    paused: false,
  });
  const [creating, setCreating] = useState(false);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [items, st, pl, fc] = await Promise.all([
        ScheduledJobsAPI.list({ workspace: fWorkspace || undefined }),
        canSchedule ? ScheduledJobsAPI.status() : Promise.resolve(null),
        PipelinesAPI.list({}),
        ForecastsAPI.list({}),
      ]);
      setJobs(items);
      setStatus(st);
      setPipelines(pl);
      setForecasts(fc);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar scheduler.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fWorkspace]);

  async function handleCreate() {
    if (!form.name || form.name.length < 2) {
      setError("Nome obrigatorio.");
      return;
    }
    if (form.job_type !== "alerts_evaluate" && !form.target_id) {
      setError("Selecione um target (pipeline ou forecast).");
      return;
    }
    setCreating(true);
    try {
      await ScheduledJobsAPI.create(form);
      setCreateOpen(false);
      await refresh();
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao criar job.",
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleRunNow(id: number) {
    setRunningId(id);
    try {
      const run = await ScheduledJobsAPI.runNow(id);
      alert(`Execucao concluida: ${run.status}${run.error_message ? `\n${run.error_message}` : ""}`);
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    } finally {
      setRunningId(null);
    }
  }

  async function handlePauseResume(job: ScheduledJob) {
    try {
      if (job.paused) {
        await ScheduledJobsAPI.resume(job.id);
      } else {
        await ScheduledJobsAPI.pause(job.id);
      }
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Remover este job agendado?")) return;
    try {
      await ScheduledJobsAPI.delete(id);
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    }
  }

  async function openHistory(job: ScheduledJob) {
    setHistoryJob(job);
    setHistoryOpen(true);
    try {
      const rs = await ScheduledJobsAPI.runs(job.id);
      setRuns(rs);
    } catch {
      setRuns([]);
    }
  }

  return (
    <PageContainer
      title="Scheduler"
      subtitle="Agende pipelines, forecasts e avaliacao de alertas com cron. APScheduler roda jobs automaticamente no backend."
      actions={
        canSchedule && (
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            + Novo job
          </Button>
        )
      }
    >
      {status && (
        <Card className="mb-4 flex flex-wrap items-center gap-4 text-sm">
          <div>
            APScheduler:{" "}
            <Badge tone={status.running ? "success" : "danger"}>
              {status.running ? "Running" : "Stopped"}
            </Badge>
          </div>
          <div>
            Jobs ativos no scheduler: <strong>{status.active_jobs}</strong>
          </div>
        </Card>
      )}

      <Card className="mb-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div>
            <label className="text-xs font-semibold text-slate-600">Workspace</label>
            <select
              className="input"
              value={fWorkspace}
              onChange={(e) => setFWorkspace(e.target.value)}
            >
              <option value="">Todos</option>
              {workspaces.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2 flex items-end text-xs text-slate-500">
            {jobs.length} job(s) · Cron formato: min hour dom month dow (UTC)
          </div>
        </div>
      </Card>

      {error && (
        <Card className="mb-4 border-rose-200 bg-rose-50 text-sm text-rose-700">{error}</Card>
      )}

      {loading ? (
        <Card className="text-sm text-slate-500">Carregando jobs...</Card>
      ) : jobs.length === 0 ? (
        <EmptyState
          title="Nenhum job agendado"
          description="Crie um job ou rode seed_scheduled_jobs.py para importar cron dos pipelines."
        />
      ) : (
        <div className="space-y-3">
          {jobs.map((j) => (
            <Card key={j.id} className="flex flex-col gap-3 md:flex-row md:items-center">
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-base font-semibold text-brand-700">{j.name}</span>
                  <Badge tone="info">{JOB_TYPE_LABELS[j.job_type] ?? j.job_type}</Badge>
                  {j.paused ? (
                    <Badge tone="warning">Paused</Badge>
                  ) : j.enabled ? (
                    <Badge tone="success">Active</Badge>
                  ) : (
                    <Badge tone="neutral">Disabled</Badge>
                  )}
                  {j.last_run_status && (
                    <Badge tone={RUN_STATUS_TONE[j.last_run_status] ?? "neutral"}>
                      last: {j.last_run_status}
                    </Badge>
                  )}
                </div>
                {j.description && (
                  <div className="mt-1 text-xs text-slate-600">{j.description}</div>
                )}
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
                  <span>
                    cron: <code className="rounded bg-slate-100 px-1">{j.cron_expression}</code>
                  </span>
                  <span>target: {j.target_name ?? j.target_id ?? "—"}</span>
                  <span>proxima: {fmtDate(j.next_run_at)}</span>
                  <span>ultima: {fmtDate(j.last_run_at)}</span>
                  <span>runs: {j.run_count}</span>
                  <span>workspace: {j.workspace}</span>
                </div>
              </div>
              {canSchedule && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => handleRunNow(j.id)}
                    disabled={runningId === j.id}
                  >
                    {runningId === j.id ? "Executando..." : "Run now"}
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => openHistory(j)}>
                    Historico
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => handlePauseResume(j)}>
                    {j.paused ? "Resume" : "Pause"}
                  </Button>
                  <Button size="sm" variant="danger" onClick={() => handleDelete(j.id)}>
                    Remover
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={createOpen}
        title="Novo scheduled job"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={handleCreate} disabled={creating}>
              {creating ? "Criando..." : "Criar"}
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-xs">
          <div>
            <label className="font-semibold text-slate-600">Nome *</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          <div>
            <label className="font-semibold text-slate-600">Tipo *</label>
            <select
              className="input"
              value={form.job_type}
              onChange={(e) =>
                setForm({
                  ...form,
                  job_type: e.target.value as ScheduledJobType,
                  target_id: null,
                })
              }
            >
              <option value="pipeline_run">Pipeline Run</option>
              <option value="forecast_train">Forecast Train</option>
              <option value="alerts_evaluate">Alerts Evaluate All</option>
            </select>
          </div>
          {form.job_type === "pipeline_run" && (
            <div>
              <label className="font-semibold text-slate-600">Pipeline *</label>
              <select
                className="input"
                value={form.target_id ?? ""}
                onChange={(e) => setForm({ ...form, target_id: Number(e.target.value) })}
              >
                <option value="">Selecione...</option>
                {pipelines.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.workspace})
                  </option>
                ))}
              </select>
            </div>
          )}
          {form.job_type === "forecast_train" && (
            <div>
              <label className="font-semibold text-slate-600">Forecast *</label>
              <select
                className="input"
                value={form.target_id ?? ""}
                onChange={(e) => setForm({ ...form, target_id: Number(e.target.value) })}
              >
                <option value="">Selecione...</option>
                {forecasts.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} ({f.workspace})
                  </option>
                ))}
              </select>
            </div>
          )}
          <div>
            <label className="font-semibold text-slate-600">Cron *</label>
            <select
              className="input mb-1"
              value={form.cron_expression}
              onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
            >
              {CRON_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label} — {p.value}
                </option>
              ))}
            </select>
            <input
              className="input font-mono"
              value={form.cron_expression}
              onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
            />
          </div>
          <div>
            <label className="font-semibold text-slate-600">Workspace</label>
            <select
              className="input"
              value={form.workspace}
              onChange={(e) => setForm({ ...form, workspace: e.target.value })}
            >
              {workspaces.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Modal>

      <Modal
        open={historyOpen}
        title={historyJob ? `Historico: ${historyJob.name}` : "Historico"}
        onClose={() => setHistoryOpen(false)}
        footer={
          <Button variant="secondary" onClick={() => setHistoryOpen(false)}>
            Fechar
          </Button>
        }
      >
        {runs.length === 0 ? (
          <div className="text-sm text-slate-500">Nenhuma execucao registrada.</div>
        ) : (
          <div className="max-h-[400px] overflow-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-100">
                <tr>
                  <th className="px-2 py-1 text-left">ID</th>
                  <th className="px-2 py-1 text-left">Status</th>
                  <th className="px-2 py-1 text-left">Inicio</th>
                  <th className="px-2 py-1 text-right">Duracao</th>
                  <th className="px-2 py-1 text-left">Trigger</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100">
                    <td className="px-2 py-1">{r.id}</td>
                    <td className="px-2 py-1">
                      <Badge tone={RUN_STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge>
                    </td>
                    <td className="px-2 py-1">{fmtDate(r.started_at)}</td>
                    <td className="px-2 py-1 text-right">
                      {r.duration_ms != null ? `${r.duration_ms}ms` : "—"}
                    </td>
                    <td className="px-2 py-1">{r.triggered_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Modal>
    </PageContainer>
  );
}
