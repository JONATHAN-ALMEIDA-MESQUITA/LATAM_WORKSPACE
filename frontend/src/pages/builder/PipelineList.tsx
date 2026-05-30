/**
 * Pipeline Studio - lista de pipelines.
 *
 * Exibe todos os pipelines com status, ultimo run, agendamento e step count.
 * Permite criar novo, abrir editor, ou rodar/arquivar/publicar inline.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PipelinesAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type { PipelineCreatePayload, PipelineSummary } from "@/types";

const STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Draft: "warning",
  Published: "success",
  Archived: "neutral",
};

const RUN_STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Success: "success",
  Failed: "danger",
  Running: "warning",
};

const BUSINESS_AREAS = ["", "Sales", "Finance", "Operations", "Supplier", "HR", "Executive"];

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function PipelineList() {
  const navigate = useNavigate();
  const permissions = useAuthStore((s) => s.permissions);
  const accessibleWorkspaces = useAuthStore((s) => s.menu?.workspaces ?? []);
  const canCreate = !!permissions?.create_pipeline;
  const canRun = !!permissions?.run_pipeline;
  const canPublish = !!permissions?.publish_pipeline || !!permissions?.publish_any;

  const [pipelines, setPipelines] = useState<PipelineSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [fWorkspace, setFWorkspace] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<PipelineCreatePayload>({
    name: "",
    description: "",
    workspace: accessibleWorkspaces[0] ?? "LATAM",
    business_area: "",
    schedule_cron: "",
  });
  const [creating, setCreating] = useState(false);

  const [runningId, setRunningId] = useState<number | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const items = await PipelinesAPI.list({
        workspace: fWorkspace || undefined,
        status: fStatus || undefined,
      });
      setPipelines(items);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar pipelines.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fWorkspace, fStatus]);

  async function handleCreate() {
    if (!form.name || form.name.length < 2) {
      setError("Nome obrigatorio (min 2 chars).");
      return;
    }
    setCreating(true);
    try {
      const p = await PipelinesAPI.create(form);
      setCreateOpen(false);
      navigate(`/builder/pipelines/${p.id}`);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao criar pipeline.",
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleRun(id: number) {
    if (!canRun) return;
    setRunningId(id);
    try {
      const run = await PipelinesAPI.run(id, "manual from list");
      if (run.status === "Failed") {
        alert(`Execucao falhou: ${run.error_message ?? "erro desconhecido"}`);
      }
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    } finally {
      setRunningId(null);
    }
  }

  async function handlePublish(id: number) {
    if (!canPublish) return;
    try {
      await PipelinesAPI.publish(id, "approved");
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    }
  }

  async function handleArchive(id: number) {
    if (!confirm("Arquivar este pipeline?")) return;
    try {
      await PipelinesAPI.archive(id, "");
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Remover pipeline definitivamente?")) return;
    try {
      await PipelinesAPI.delete(id);
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    }
  }

  return (
    <PageContainer
      title="Pipeline Studio"
      subtitle="ETL Builder visual: defina sources, transformacoes e targets. Output vira dataset disponivel no Metric Builder."
      actions={
        canCreate && (
          <Button onClick={() => setCreateOpen(true)} variant="primary">
            + Novo pipeline
          </Button>
        )
      }
    >
      <Card className="mb-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
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
            <label className="text-xs font-semibold text-slate-600">Status</label>
            <select className="input" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
              <option value="">Todos</option>
              <option>Draft</option>
              <option>Published</option>
              <option>Archived</option>
            </select>
          </div>
          <div className="md:col-span-2 flex items-end">
            <div className="text-xs text-slate-500">
              {pipelines.length} pipeline(s)
            </div>
          </div>
        </div>
      </Card>

      {error && (
        <Card className="mb-4 border-rose-200 bg-rose-50 text-sm text-rose-700">{error}</Card>
      )}

      {loading ? (
        <Card className="text-sm text-slate-500">Carregando pipelines...</Card>
      ) : pipelines.length === 0 ? (
        <EmptyState
          title="Nenhum pipeline encontrado"
          description="Crie seu primeiro pipeline para transformar dados e gerar novos datasets."
        />
      ) : (
        <div className="space-y-3">
          {pipelines.map((p) => (
            <Card key={p.id} className="flex flex-col gap-3 md:flex-row md:items-center">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    className="text-base font-semibold text-brand-700 hover:underline"
                    onClick={() => navigate(`/builder/pipelines/${p.id}`)}
                  >
                    {p.name}
                  </button>
                  <Badge tone={STATUS_TONE[p.status] ?? "neutral"}>{p.status}</Badge>
                  {p.last_run_status && (
                    <Badge tone={RUN_STATUS_TONE[p.last_run_status] ?? "neutral"}>
                      run: {p.last_run_status}
                    </Badge>
                  )}
                </div>
                {p.description && (
                  <div className="mt-1 text-xs text-slate-600">{p.description}</div>
                )}
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
                  <span>
                    <strong>{p.step_count}</strong> steps
                  </span>
                  <span>workspace: {p.workspace}</span>
                  {p.business_area && <span>area: {p.business_area}</span>}
                  {p.schedule_cron && (
                    <span>
                      cron: <code className="rounded bg-slate-100 px-1">{p.schedule_cron}</code>
                    </span>
                  )}
                  <span>ultima execucao: {fmtDate(p.last_run_at)}</span>
                  <span>atualizado: {fmtDate(p.updated_at)}</span>
                  <span>por: {p.created_by}</span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => navigate(`/builder/pipelines/${p.id}`)}
                >
                  Editar
                </Button>
                {canRun && (
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => handleRun(p.id)}
                    disabled={runningId === p.id || p.step_count === 0}
                  >
                    {runningId === p.id ? "Executando..." : "Run now"}
                  </Button>
                )}
                {canPublish && p.status === "Draft" && (
                  <Button size="sm" variant="secondary" onClick={() => handlePublish(p.id)}>
                    Publicar
                  </Button>
                )}
                {p.status !== "Archived" && (
                  <Button size="sm" variant="secondary" onClick={() => handleArchive(p.id)}>
                    Arquivar
                  </Button>
                )}
                {canCreate && (
                  <Button size="sm" variant="danger" onClick={() => handleDelete(p.id)}>
                    Remover
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Modal de criacao */}
      <Modal
        open={createOpen}
        title="Novo pipeline"
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
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-slate-600">Nome *</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Ex: Sales Brazil - Top Clients"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Descricao</label>
            <textarea
              className="input min-h-[60px]"
              value={form.description ?? ""}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="O que este pipeline faz?"
            />
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-600">Workspace</label>
              <select
                className="input"
                value={form.workspace ?? ""}
                onChange={(e) => setForm({ ...form, workspace: e.target.value })}
              >
                {accessibleWorkspaces.map((w) => (
                  <option key={w} value={w}>
                    {w}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Business area</label>
              <select
                className="input"
                value={form.business_area ?? ""}
                onChange={(e) => setForm({ ...form, business_area: e.target.value })}
              >
                {BUSINESS_AREAS.map((a) => (
                  <option key={a} value={a}>
                    {a || "(nenhuma)"}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">
              Schedule cron (informativo, sem executor real)
            </label>
            <input
              className="input font-mono text-xs"
              value={form.schedule_cron ?? ""}
              onChange={(e) => setForm({ ...form, schedule_cron: e.target.value })}
              placeholder="Ex: 0 6 * * *  (todo dia 06:00)"
            />
          </div>
        </div>
      </Modal>
    </PageContainer>
  );
}
