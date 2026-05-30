/**
 * Admin — System Jobs / platform health (Phase 8).
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AdminAPI, ScheduledJobsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAuthStore } from "@/store/authStore";
import type { ScheduledJob, ScheduledJobRun, SystemStatus } from "@/types";

export default function SystemJobsDashboard() {
  const canView = !!useAuthStore((s) => s.permissions?.view_admin);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [recentRuns, setRecentRuns] = useState<ScheduledJobRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canView) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const [st, j] = await Promise.all([
          AdminAPI.systemStatus(),
          ScheduledJobsAPI.list(),
        ]);
        setStatus(st);
        setJobs(j);
        const runsNested = await Promise.all(
          j.slice(0, 3).map((job) => ScheduledJobsAPI.runs(job.id, 5)),
        );
        setRecentRuns(runsNested.flat().slice(0, 15));
      } catch (e: unknown) {
        setError(
          (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            "Falha ao carregar status.",
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [canView]);

  if (!canView) {
    return (
      <PageContainer title="System Jobs" subtitle="Saúde do sistema">
        <EmptyState title="Sem permissão" description="Capability view_admin necessária." />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="System Jobs"
      subtitle="Visão executiva da saúde da plataforma e do scheduler."
      actions={
        <Link to="/builder/scheduler">
          <Button variant="secondary">Abrir Scheduler</Button>
        </Link>
      }
    >
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading || !status ? (
        <p className="text-sm text-slate-500">Carregando...</p>
      ) : (
        <>
          <div className="mb-6 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card title="Plataforma">
              <p className="text-lg font-semibold text-emerald-700">{status.status.toUpperCase()}</p>
              <p className="text-xs text-slate-500">
                {status.app} v{status.version} · {status.environment}
              </p>
            </Card>
            <Card
              title="APScheduler"
              actions={
                <Badge tone={status.scheduler_running ? "success" : "danger"}>
                  {status.scheduler_running ? "Running" : "Stopped"}
                </Badge>
              }
            >
              <p className="text-2xl font-bold">{status.scheduler_active_jobs}</p>
              <p className="text-xs text-slate-500">jobs ativos</p>
            </Card>
            <Card title="Falhas (runs)">
              <p className="text-2xl font-bold text-red-600">{status.recent_failed_jobs}</p>
              <p className="text-xs text-slate-500">execuções com status Failed</p>
            </Card>
            <Card title="Database">
              <p className="truncate font-mono text-xs text-slate-600">{status.database_url}</p>
            </Card>
          </div>

          <Card title="Entidades na plataforma" className="mb-6">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
              {Object.entries(status.entity_counts).map(([k, v]) => (
                <div key={k} className="rounded border border-slate-200 p-3 text-center">
                  <p className="text-xl font-bold">{v}</p>
                  <p className="text-xs capitalize text-slate-500">{k.replace(/_/g, " ")}</p>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Scheduled jobs">
              <ul className="space-y-2 text-sm">
                {jobs.map((j) => (
                  <li key={j.id} className="flex items-center justify-between border-b border-slate-100 py-2">
                    <span>{j.name}</span>
                    <Badge tone={j.enabled && !j.paused ? "success" : "neutral"}>
                      {j.enabled && !j.paused ? "Active" : "Paused"}
                    </Badge>
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Execuções recentes">
              <ul className="space-y-2 text-xs">
                {recentRuns.map((r) => (
                  <li key={r.id} className="flex items-center justify-between border-b border-slate-100 py-1.5">
                    <span>
                      Job #{r.job_id} · {r.triggered_by}
                    </span>
                    <Badge tone={r.status === "Success" ? "success" : r.status === "Failed" ? "danger" : "warning"}>
                      {r.status}
                    </Badge>
                  </li>
                ))}
                {recentRuns.length === 0 && (
                  <li className="text-slate-500">Nenhuma execução recente.</li>
                )}
              </ul>
            </Card>
          </div>
        </>
      )}
    </PageContainer>
  );
}
