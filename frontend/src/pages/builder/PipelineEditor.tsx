/**
 * Pipeline Editor - editor visual de um pipeline (linear vertical).
 *
 * Layout em 3 colunas:
 *   [paleta] [pipeline canvas (cards verticais)] [config + preview do step selecionado]
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { DatasetsAPI, PipelinesAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { PipelineStepConfig } from "@/components/pipeline/PipelineStepConfig";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type {
  DatasetSummary,
  Pipeline,
  PipelinePreviewResult,
  PipelineRun,
  PipelineStep,
  StepType,
} from "@/types";

// Catalogo de tipos de step para a paleta
const STEP_PALETTE: { type: StepType; label: string; icon: string; description: string }[] = [
  { type: "source", label: "Source", icon: "DB", description: "Le um dataset" },
  { type: "filter", label: "Filter", icon: "FL", description: "Filtra linhas (AND)" },
  { type: "select", label: "Select", icon: "SL", description: "Seleciona/renomeia colunas" },
  { type: "computed", label: "Computed", icon: "FX", description: "Coluna calculada (expr)" },
  { type: "group_by", label: "Group By", icon: "GB", description: "Agrupa + agrega" },
  { type: "join", label: "Join", icon: "JN", description: "Junta com outro dataset" },
  { type: "union", label: "Union", icon: "UN", description: "Concatena datasets" },
  { type: "sort", label: "Sort", icon: "SO", description: "Ordena por colunas" },
  { type: "limit", label: "Limit", icon: "LM", description: "Top N rows" },
  { type: "target", label: "Target", icon: "TG", description: "Grava como dataset" },
];

const STEP_COLORS: Record<string, string> = {
  source: "bg-emerald-50 border-emerald-300 text-emerald-800",
  filter: "bg-amber-50 border-amber-300 text-amber-800",
  select: "bg-blue-50 border-blue-300 text-blue-800",
  computed: "bg-purple-50 border-purple-300 text-purple-800",
  group_by: "bg-rose-50 border-rose-300 text-rose-800",
  join: "bg-indigo-50 border-indigo-300 text-indigo-800",
  union: "bg-cyan-50 border-cyan-300 text-cyan-800",
  sort: "bg-slate-50 border-slate-300 text-slate-800",
  limit: "bg-slate-50 border-slate-300 text-slate-800",
  target: "bg-emerald-50 border-emerald-400 text-emerald-900",
};

const RUN_STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Success: "success",
  Failed: "danger",
  Running: "warning",
};

const STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Draft: "warning",
  Published: "success",
  Archived: "neutral",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function PipelineEditor() {
  const { id } = useParams<{ id: string }>();
  const pipelineId = id ? Number(id) : 0;
  const navigate = useNavigate();
  const permissions = useAuthStore((s) => s.permissions);
  const canEdit = !!permissions?.create_pipeline;
  const canRun = !!permissions?.run_pipeline;
  const canPublish = !!permissions?.publish_pipeline || !!permissions?.publish_any;

  const [pipeline, setPipeline] = useState<Pipeline | null>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedStepId, setSelectedStepId] = useState<number | null>(null);
  const [preview, setPreview] = useState<PipelinePreviewResult | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [runsOpen, setRunsOpen] = useState(false);
  const [running, setRunning] = useState(false);
  // Ultimo run (usado pra highlight do step que falhou no canvas)
  const [lastRun, setLastRun] = useState<PipelineRun | null>(null);
  // Erro estruturado vindo de /preview ({message, failed_step_index, ...})
  const [previewFailure, setPreviewFailure] = useState<{
    message: string;
    failed_step_index?: number | null;
    failed_step_name?: string | null;
    failed_step_type?: string | null;
  } | null>(null);

  const refreshPipeline = useCallback(async () => {
    if (!pipelineId) return;
    try {
      const p = await PipelinesAPI.get(pipelineId);
      setPipeline(p);
      if (selectedStepId == null && p.steps.length > 0) {
        setSelectedStepId(p.steps[0].id);
      }
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar pipeline.",
      );
    }
  }, [pipelineId, selectedStepId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      PipelinesAPI.get(pipelineId).then((p) => {
        setPipeline(p);
        if (p.steps.length > 0) setSelectedStepId(p.steps[0].id);
      }),
      DatasetsAPI.list(),
      PipelinesAPI.runs(pipelineId, 1).then((rs) => setLastRun(rs[0] ?? null)),
    ])
      .catch((err) => {
        setError(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            "Falha ao carregar editor.",
        );
      })
      .finally(() => setLoading(false));
    DatasetsAPI.list().then(setDatasets);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipelineId]);

  const selectedStep = useMemo(
    () => pipeline?.steps.find((s) => s.id === selectedStepId) ?? null,
    [pipeline, selectedStepId],
  );

  const selectedIndex = useMemo(
    () => (pipeline && selectedStep ? pipeline.steps.findIndex((s) => s.id === selectedStep.id) : -1),
    [pipeline, selectedStep],
  );

  // Colunas disponiveis = preview do step ANTERIOR ao selecionado
  const [upstreamColumns, setUpstreamColumns] = useState<{ name: string; dtype: string }[]>([]);

  const loadUpstreamColumns = useCallback(async () => {
    if (!pipeline || selectedIndex <= 0) {
      setUpstreamColumns([]);
      return;
    }
    try {
      const res = await PipelinesAPI.preview(pipelineId, {
        up_to_index: selectedIndex - 1,
        sample_rows: 5,
      });
      setUpstreamColumns(res.dataframe_schema ?? []);
    } catch {
      setUpstreamColumns([]);
    }
  }, [pipeline, pipelineId, selectedIndex]);

  useEffect(() => {
    loadUpstreamColumns();
    setPreview(null);
    setPreviewError(null);
    setPreviewFailure(null);
  }, [loadUpstreamColumns, selectedStepId]);

  async function handlePreviewSelected() {
    if (!pipeline || selectedIndex < 0) return;
    setPreviewError(null);
    setPreviewFailure(null);
    setPreviewing(true);
    try {
      const res = await PipelinesAPI.preview(pipelineId, {
        up_to_index: selectedIndex,
        sample_rows: 50,
      });
      setPreview(res);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      // Backend pode mandar detail estruturado (StepFailure) ou string
      if (detail && typeof detail === "object") {
        const d = detail as {
          message?: string;
          failed_step_index?: number | null;
          failed_step_name?: string | null;
          failed_step_type?: string | null;
        };
        setPreviewFailure({
          message: d.message ?? "Falha no preview.",
          failed_step_index: d.failed_step_index ?? null,
          failed_step_name: d.failed_step_name ?? null,
          failed_step_type: d.failed_step_type ?? null,
        });
        setPreviewError(d.message ?? "Falha no preview.");
      } else {
        setPreviewError(typeof detail === "string" ? detail : "Falha no preview.");
      }
    } finally {
      setPreviewing(false);
    }
  }

  async function handleAddStep(type: StepType) {
    if (!canEdit) return;
    const palette = STEP_PALETTE.find((p) => p.type === type);
    try {
      const s = await PipelinesAPI.createStep(pipelineId, {
        step_type: type,
        name: palette?.label ?? type,
        config: {},
      });
      await refreshPipeline();
      setSelectedStepId(s.id);
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    }
  }

  async function handleUpdateStepConfig(step: PipelineStep, nextConfig: Record<string, unknown>) {
    // Update otimista local
    setPipeline((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        steps: prev.steps.map((s) => (s.id === step.id ? { ...s, config: nextConfig } : s)),
      };
    });
    try {
      await PipelinesAPI.updateStep(pipelineId, step.id, { config: nextConfig });
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
      await refreshPipeline();
    }
  }

  async function handleRenameStep(step: PipelineStep, name: string) {
    setPipeline((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        steps: prev.steps.map((s) => (s.id === step.id ? { ...s, name } : s)),
      };
    });
    try {
      await PipelinesAPI.updateStep(pipelineId, step.id, { name });
    } catch {
      await refreshPipeline();
    }
  }

  async function handleMoveStep(step: PipelineStep, dir: -1 | 1) {
    if (!pipeline) return;
    const idx = pipeline.steps.findIndex((s) => s.id === step.id);
    const swapIdx = idx + dir;
    if (swapIdx < 0 || swapIdx >= pipeline.steps.length) return;
    const newOrder = [...pipeline.steps];
    [newOrder[idx], newOrder[swapIdx]] = [newOrder[swapIdx], newOrder[idx]];
    try {
      await PipelinesAPI.reorderSteps(pipelineId, newOrder.map((s) => s.id));
      await refreshPipeline();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    }
  }

  async function handleDeleteStep(step: PipelineStep) {
    if (!confirm(`Remover step "${step.name}"?`)) return;
    try {
      await PipelinesAPI.deleteStep(pipelineId, step.id);
      if (selectedStepId === step.id) setSelectedStepId(null);
      await refreshPipeline();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    }
  }

  async function handleRun() {
    if (!pipeline) return;
    setRunning(true);
    try {
      const run = await PipelinesAPI.run(pipelineId, "manual from editor");
      setLastRun(run);
      await refreshPipeline();
      if (run.status === "Success") {
        alert(
          `Pipeline executado com sucesso!\n` +
            `Rows: ${run.rows_in} -> ${run.rows_out} | Duracao: ${run.duration_ms}ms\n` +
            `Dataset gerado id: ${run.target_dataset_id ?? "—"}`,
        );
      } else {
        // Foca no step que falhou e abre o preview pra dar contexto
        if (
          run.failed_step_index != null &&
          pipeline.steps[run.failed_step_index]
        ) {
          setSelectedStepId(pipeline.steps[run.failed_step_index].id);
        }
        const stepDesc =
          run.failed_step_index != null
            ? `Step #${run.failed_step_index + 1} (${run.failed_step_name} / ${run.failed_step_type})`
            : "Step desconhecido";
        alert(`Pipeline FALHOU em ${stepDesc}:\n\n${run.error_message ?? "erro"}`);
      }
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    } finally {
      setRunning(false);
    }
  }

  async function handleOpenRuns() {
    setRunsOpen(true);
    try {
      const rs = await PipelinesAPI.runs(pipelineId, 50);
      setRuns(rs);
    } catch {
      setRuns([]);
    }
  }

  async function handlePublish() {
    if (!pipeline || !canPublish) return;
    try {
      await PipelinesAPI.publish(pipelineId, "");
      await refreshPipeline();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha",
      );
    }
  }

  if (loading) {
    return (
      <PageContainer title="Carregando...">
        <Card className="text-sm text-slate-500">Carregando editor...</Card>
      </PageContainer>
    );
  }

  if (error || !pipeline) {
    return (
      <PageContainer
        title="Erro"
        actions={
          <Button variant="secondary" onClick={() => navigate("/builder/pipelines")}>
            Voltar
          </Button>
        }
      >
        <Card className="border-rose-200 bg-rose-50 text-sm text-rose-700">{error ?? "—"}</Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={pipeline.name}
      subtitle={pipeline.description || "Pipeline ETL - arraste steps, configure e execute."}
      actions={
        <div className="flex flex-wrap gap-2">
          <Badge tone={STATUS_TONE[pipeline.status] ?? "neutral"}>{pipeline.status}</Badge>
          {pipeline.last_run_status && (
            <Badge tone={RUN_STATUS_TONE[pipeline.last_run_status] ?? "neutral"}>
              ultimo run: {pipeline.last_run_status}
            </Badge>
          )}
          <Button size="sm" variant="secondary" onClick={handleOpenRuns}>
            Historico
          </Button>
          {canRun && (
            <Button
              size="sm"
              variant="primary"
              onClick={handleRun}
              disabled={running || pipeline.steps.length === 0}
            >
              {running ? "Executando..." : "Run now"}
            </Button>
          )}
          {canPublish && pipeline.status === "Draft" && (
            <Button size="sm" variant="secondary" onClick={handlePublish}>
              Publicar
            </Button>
          )}
          <Button size="sm" variant="secondary" onClick={() => navigate("/builder/pipelines")}>
            Voltar
          </Button>
        </div>
      }
    >
      {lastRun?.status === "Failed" && (
        <Card className="mb-3 border-rose-300 bg-rose-50">
          <div className="flex items-start gap-3 text-sm">
            <span className="rounded bg-rose-600 px-2 py-0.5 text-xs font-bold text-white">
              ULTIMO RUN FALHOU
            </span>
            <div className="flex-1">
              <div className="font-semibold text-rose-800">
                {lastRun.failed_step_index != null
                  ? `Step #${lastRun.failed_step_index + 1}: ${lastRun.failed_step_name}`
                  : "Step desconhecido"}{" "}
                {lastRun.failed_step_type && (
                  <span className="font-mono text-xs text-rose-600">
                    ({lastRun.failed_step_type})
                  </span>
                )}
              </div>
              <div className="text-xs text-rose-700">{lastRun.error_message}</div>
              <div className="mt-1 text-[11px] text-rose-500">
                executado em {fmtDate(lastRun.started_at)} por {lastRun.triggered_by}
                {lastRun.failed_step_index != null && pipeline.steps[lastRun.failed_step_index] && (
                  <button
                    type="button"
                    className="ml-2 text-brand-600 hover:underline"
                    onClick={() => setSelectedStepId(pipeline.steps[lastRun.failed_step_index!].id)}
                  >
                    abrir step
                  </button>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-12 gap-4">
        {/* Paleta */}
        <Card className="col-span-12 md:col-span-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
            Paleta
          </div>
          <div className="space-y-1">
            {STEP_PALETTE.map((p) => (
              <button
                key={p.type}
                type="button"
                onClick={() => handleAddStep(p.type)}
                disabled={!canEdit}
                className={`w-full rounded border px-2 py-1.5 text-left text-xs hover:shadow-sm ${
                  STEP_COLORS[p.type]
                } ${canEdit ? "" : "opacity-50 cursor-not-allowed"}`}
                title={p.description}
              >
                <div className="font-semibold">+ {p.label}</div>
                <div className="text-[10px] opacity-75">{p.description}</div>
              </button>
            ))}
          </div>
        </Card>

        {/* Pipeline canvas */}
        <Card className="col-span-12 md:col-span-5">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
            Pipeline ({pipeline.steps.length} steps)
          </div>
          {pipeline.steps.length === 0 ? (
            <div className="rounded border-2 border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500">
              Adicione um <strong>Source</strong> da paleta para comecar.
            </div>
          ) : (
            <div className="space-y-2">
              {pipeline.steps.map((s, idx) => {
                const isSelected = s.id === selectedStepId;
                const failedHere =
                  lastRun?.status === "Failed" && lastRun.failed_step_index === idx;
                const previewFailedHere =
                  previewFailure?.failed_step_index === idx;
                const hasError = failedHere || previewFailedHere;
                return (
                  <div key={s.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedStepId(s.id)}
                      className={`block w-full rounded border-2 px-3 py-2 text-left transition ${
                        STEP_COLORS[s.step_type]
                      } ${
                        isSelected ? "ring-2 ring-offset-1 ring-brand-500" : "hover:shadow"
                      } ${hasError ? "!border-rose-500 bg-rose-50" : ""}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="rounded bg-white/70 px-1.5 py-0.5 text-[10px] font-mono">
                            {idx + 1}
                          </span>
                          <span className="font-semibold truncate text-sm">{s.name}</span>
                          <span className="text-[10px] uppercase opacity-70">{s.step_type}</span>
                          {hasError && (
                            <span
                              className="rounded bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold text-white"
                              title={
                                failedHere
                                  ? lastRun?.error_message ?? "Falhou no ultimo run"
                                  : previewFailure?.message
                              }
                            >
                              ERRO
                            </span>
                          )}
                        </div>
                        <div className="flex gap-1">
                          {canEdit && (
                            <>
                              <button
                                type="button"
                                className="text-xs hover:underline"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleMoveStep(s, -1);
                                }}
                                disabled={idx === 0}
                                title="mover para cima"
                              >
                                ↑
                              </button>
                              <button
                                type="button"
                                className="text-xs hover:underline"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleMoveStep(s, 1);
                                }}
                                disabled={idx === pipeline.steps.length - 1}
                                title="mover para baixo"
                              >
                                ↓
                              </button>
                              <button
                                type="button"
                                className="text-xs text-rose-700 hover:underline"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteStep(s);
                                }}
                                title="remover"
                              >
                                x
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                    </button>
                    {idx < pipeline.steps.length - 1 && (
                      <div className="my-1 text-center text-slate-400 text-xs">↓</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Config + preview */}
        <Card className="col-span-12 md:col-span-5">
          {selectedStep ? (
            <>
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] uppercase text-slate-500">
                    Step #{selectedIndex + 1} - {selectedStep.step_type}
                  </div>
                  <input
                    className="input mt-1"
                    value={selectedStep.name}
                    onChange={(e) => handleRenameStep(selectedStep, e.target.value)}
                    disabled={!canEdit}
                  />
                </div>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={handlePreviewSelected}
                  disabled={previewing}
                >
                  {previewing ? "..." : "Preview"}
                </Button>
              </div>

              <div className="mb-3">
                <PipelineStepConfig
                  stepType={selectedStep.step_type}
                  config={selectedStep.config}
                  onChange={(next) => handleUpdateStepConfig(selectedStep, next)}
                  datasets={datasets}
                  upstreamColumns={upstreamColumns}
                />
              </div>

              {/* Preview area */}
              {previewFailure ? (
                <div className="mb-2 rounded border border-rose-300 bg-rose-50 p-2 text-xs text-rose-800">
                  <div className="font-semibold">
                    Falha no step{" "}
                    {previewFailure.failed_step_index != null
                      ? `#${previewFailure.failed_step_index + 1}`
                      : ""}{" "}
                    {previewFailure.failed_step_name && (
                      <span>
                        — {previewFailure.failed_step_name}{" "}
                        <span className="font-mono text-[10px] opacity-70">
                          ({previewFailure.failed_step_type})
                        </span>
                      </span>
                    )}
                  </div>
                  <div className="mt-1">{previewFailure.message}</div>
                </div>
              ) : previewError ? (
                <div className="mb-2 rounded border border-rose-300 bg-rose-50 p-2 text-xs text-rose-700">
                  {previewError}
                </div>
              ) : null}
              {preview && (
                <div className="rounded border bg-slate-50 p-2">
                  <div className="mb-1 flex items-center justify-between text-[11px] text-slate-600">
                    <span>
                      Output do step {selectedIndex + 1}: {preview.total_rows} rows,{" "}
                      {preview.columns.length} colunas
                    </span>
                  </div>
                  <div className="max-h-72 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead className="sticky top-0 bg-slate-100">
                        <tr>
                          {preview.columns.map((c) => (
                            <th key={c} className="px-2 py-1 text-left font-semibold">
                              {c}
                              <div className="text-[9px] font-normal text-slate-400">
                                {preview.dataframe_schema?.find((s) => s.name === c)?.dtype}
                              </div>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.rows.slice(0, 30).map((row, i) => (
                          <tr
                            key={i}
                            className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}
                          >
                            {preview.columns.map((c) => (
                              <td key={c} className="px-2 py-1 whitespace-nowrap">
                                {row[c] == null ? (
                                  <span className="text-slate-300">null</span>
                                ) : typeof row[c] === "number" ? (
                                  (row[c] as number).toLocaleString(undefined, {
                                    maximumFractionDigits: 2,
                                  })
                                ) : (
                                  String(row[c])
                                )}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-slate-500">
              Selecione um step a esquerda para configurar e pre-visualizar.
            </div>
          )}
        </Card>
      </div>

      {/* Modal de historico de runs */}
      <Modal open={runsOpen} title="Historico de execucoes" onClose={() => setRunsOpen(false)}>
        {runs.length === 0 ? (
          <div className="text-sm text-slate-500">Nenhuma execucao registrada.</div>
        ) : (
          <div className="space-y-2">
            {runs.map((r) => (
              <div key={r.id} className="rounded border p-2 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge tone={RUN_STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge>
                    <span className="text-slate-500">por {r.triggered_by}</span>
                  </div>
                  <span className="text-slate-500">{fmtDate(r.started_at)}</span>
                </div>
                <div className="mt-1 text-[11px] text-slate-600">
                  Duracao: {r.duration_ms ?? "—"} ms | Rows: {r.rows_in ?? "—"} →{" "}
                  {r.rows_out ?? "—"} | Target dataset: {r.target_dataset_id ?? "—"}
                </div>
                {r.error_message && (
                  <div className="mt-1 rounded bg-rose-50 p-1 text-rose-700">
                    {r.failed_step_index != null && (
                      <div className="text-[11px] font-semibold">
                        Step #{r.failed_step_index + 1}: {r.failed_step_name}{" "}
                        <span className="font-mono opacity-70">({r.failed_step_type})</span>
                      </div>
                    )}
                    <div>{r.error_message}</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Modal>
    </PageContainer>
  );
}
