/**
 * Forecasting Studio - lista de forecasts.
 *
 * Lista todos os forecasts com algoritmo, status, ultima execucao e metricas.
 * Permite criar novo, abrir editor, treinar/publicar/arquivar inline.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DatasetsAPI, ForecastsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type {
  DatasetSummary,
  ForecastAlgorithm,
  ForecastCreatePayload,
  ForecastFrequency,
  ForecastSummary,
} from "@/types";

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

const ALGORITHM_LABELS: Record<ForecastAlgorithm, string> = {
  naive_seasonal: "Naive Seasonal",
  linear_trend: "Linear Trend",
  holt_winters: "Holt-Winters",
};

const FREQUENCY_LABELS: Record<ForecastFrequency, string> = {
  D: "Diaria",
  W: "Semanal",
  M: "Mensal",
  Q: "Trimestral",
  Y: "Anual",
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

function fmtMetric(v: number | null | undefined, suffix = ""): string {
  if (v === null || v === undefined) return "—";
  if (suffix === "%") return `${v.toFixed(2)}%`;
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k${suffix}`;
  return `${v.toFixed(2)}${suffix}`;
}

function bestMape(metrics: ForecastSummary["last_metrics"]): number | null {
  if (!metrics) return null;
  const vals = Object.values(metrics)
    .map((m) => (typeof m.mape === "number" ? m.mape : null))
    .filter((v): v is number => v !== null);
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

export default function ForecastList() {
  const navigate = useNavigate();
  const permissions = useAuthStore((s) => s.permissions);
  const accessibleWorkspaces = useAuthStore((s) => s.menu?.workspaces ?? []);
  const canCreate = !!permissions?.create_forecast;
  const canPublish = !!permissions?.publish_forecast || !!permissions?.publish_any;

  const [forecasts, setForecasts] = useState<ForecastSummary[]>([]);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [fWorkspace, setFWorkspace] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<ForecastCreatePayload>({
    name: "",
    description: "",
    workspace: accessibleWorkspaces[0] ?? "LATAM",
    business_area: "",
    source_dataset_id: 0,
    target_column: "",
    date_column: "",
    frequency: "M",
    horizon: 12,
    holdout_periods: 6,
    algorithm: "holt_winters",
    group_by: [],
    aggregation: "sum",
  });
  const [creating, setCreating] = useState(false);
  const [trainingId, setTrainingId] = useState<number | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [items, ds] = await Promise.all([
        ForecastsAPI.list({
          workspace: fWorkspace || undefined,
          status: fStatus || undefined,
        }),
        DatasetsAPI.list({}),
      ]);
      setForecasts(items);
      setDatasets(ds);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar forecasts.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fWorkspace, fStatus]);

  const selectedDataset = useMemo(
    () => datasets.find((d) => d.id === form.source_dataset_id) ?? null,
    [datasets, form.source_dataset_id],
  );

  async function handleCreate() {
    if (!form.name || form.name.length < 2) {
      setError("Nome obrigatorio (min 2 chars).");
      return;
    }
    if (!form.source_dataset_id) {
      setError("Selecione um dataset de origem.");
      return;
    }
    if (!form.target_column || !form.date_column) {
      setError("Informe target_column e date_column.");
      return;
    }
    setCreating(true);
    try {
      const f = await ForecastsAPI.create(form);
      setCreateOpen(false);
      navigate(`/builder/forecasts/${f.id}`);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao criar forecast.",
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleTrain(id: number) {
    setTrainingId(id);
    try {
      const r = await ForecastsAPI.train(id);
      alert(
        `Treino OK!\n\nGrupos: ${r.groups_count}\nrows_in: ${r.rows_in}\nrows_forecast: ${r.rows_forecast}\n\n` +
          Object.entries(r.metrics)
            .slice(0, 5)
            .map(
              ([k, m]) =>
                `${k}: MAE=${fmtMetric(m.mae)} RMSE=${fmtMetric(m.rmse)} MAPE=${fmtMetric(m.mape, "%")}`,
            )
            .join("\n"),
      );
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(`Falha no treino: ${detail}`);
    } finally {
      setTrainingId(null);
    }
  }

  async function handlePublish(id: number) {
    if (!canPublish) return;
    if (!confirm("Publicar este forecast?\n\nIsso re-treina o modelo e grava o output como Dataset."))
      return;
    try {
      await ForecastsAPI.publish(id, "approved");
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(`Falha ao publicar: ${detail}`);
    }
  }

  async function handleArchive(id: number) {
    if (!confirm("Arquivar este forecast?")) return;
    try {
      await ForecastsAPI.archive(id, "");
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Remover forecast definitivamente?")) return;
    try {
      await ForecastsAPI.delete(id);
      await refresh();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Falha";
      alert(detail);
    }
  }

  return (
    <PageContainer
      title="Forecasting Studio"
      subtitle="Treine modelos preditivos sobre datasets/metrics, valide com backtest (MAE/RMSE/MAPE) e publique o output como dataset disponivel em dashboards."
      actions={
        canCreate && (
          <Button onClick={() => setCreateOpen(true)} variant="primary">
            + Novo forecast
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
            <div className="text-xs text-slate-500">{forecasts.length} forecast(s)</div>
          </div>
        </div>
      </Card>

      {error && (
        <Card className="mb-4 border-rose-200 bg-rose-50 text-sm text-rose-700">{error}</Card>
      )}

      {loading ? (
        <Card className="text-sm text-slate-500">Carregando forecasts...</Card>
      ) : forecasts.length === 0 ? (
        <EmptyState
          title="Nenhum forecast encontrado"
          description="Crie seu primeiro forecast para projetar valores futuros sobre datasets historicos."
        />
      ) : (
        <div className="space-y-3">
          {forecasts.map((f) => {
            const avgMape = bestMape(f.last_metrics);
            return (
              <Card key={f.id} className="flex flex-col gap-3 md:flex-row md:items-center">
                <div className="flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="text-base font-semibold text-brand-700 hover:underline"
                      onClick={() => navigate(`/builder/forecasts/${f.id}`)}
                    >
                      {f.name}
                    </button>
                    <Badge tone={STATUS_TONE[f.status] ?? "neutral"}>{f.status}</Badge>
                    <Badge tone="info">{ALGORITHM_LABELS[f.algorithm] ?? f.algorithm}</Badge>
                    <Badge tone="neutral">
                      {FREQUENCY_LABELS[f.frequency] ?? f.frequency} · horizon {f.horizon}
                    </Badge>
                    {f.last_run_status && (
                      <Badge tone={RUN_STATUS_TONE[f.last_run_status] ?? "neutral"}>
                        run: {f.last_run_status}
                      </Badge>
                    )}
                    {avgMape !== null && (
                      <Badge tone={avgMape < 15 ? "success" : avgMape < 30 ? "warning" : "danger"}>
                        MAPE medio: {avgMape.toFixed(2)}%
                      </Badge>
                    )}
                  </div>
                  {f.description && (
                    <div className="mt-1 text-xs text-slate-600">{f.description}</div>
                  )}
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500">
                    <span>workspace: {f.workspace}</span>
                    {f.business_area && <span>area: {f.business_area}</span>}
                    <span>ultima execucao: {fmtDate(f.last_run_at)}</span>
                    <span>atualizado: {fmtDate(f.updated_at)}</span>
                    <span>por: {f.created_by}</span>
                    {f.output_dataset_id && <span>output: dataset #{f.output_dataset_id}</span>}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => navigate(`/builder/forecasts/${f.id}`)}
                  >
                    Abrir
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => handleTrain(f.id)}
                    disabled={trainingId === f.id}
                  >
                    {trainingId === f.id ? "Treinando..." : "Train"}
                  </Button>
                  {canPublish && f.status !== "Published" && (
                    <Button size="sm" variant="secondary" onClick={() => handlePublish(f.id)}>
                      Publicar
                    </Button>
                  )}
                  {f.status !== "Archived" && (
                    <Button size="sm" variant="secondary" onClick={() => handleArchive(f.id)}>
                      Arquivar
                    </Button>
                  )}
                  {canCreate && (
                    <Button size="sm" variant="danger" onClick={() => handleDelete(f.id)}>
                      Remover
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Modal de criacao */}
      <Modal
        open={createOpen}
        title="Novo forecast"
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
              placeholder="Ex: Revenue Forecast LATAM 12M"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Descricao</label>
            <textarea
              className="input min-h-[60px]"
              value={form.description ?? ""}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-600">Workspace *</label>
              <select
                className="input"
                value={form.workspace}
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
            <label className="text-xs font-semibold text-slate-600">Dataset de origem *</label>
            <select
              className="input"
              value={form.source_dataset_id}
              onChange={(e) =>
                setForm({ ...form, source_dataset_id: Number(e.target.value) })
              }
            >
              <option value={0}>Selecione um dataset...</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.workspace}) - {d.row_count} linhas
                </option>
              ))}
            </select>
            {selectedDataset && (
              <div className="mt-1 text-[11px] text-slate-500">
                Colunas detectadas via /datasets/&lt;id&gt;/columns no editor.
              </div>
            )}
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-600">Coluna alvo (numerica) *</label>
              <input
                className="input"
                value={form.target_column}
                onChange={(e) => setForm({ ...form, target_column: e.target.value })}
                placeholder="Ex: revenue"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Coluna de data *</label>
              <input
                className="input"
                value={form.date_column}
                onChange={(e) => setForm({ ...form, date_column: e.target.value })}
                placeholder="Ex: date"
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div>
              <label className="text-xs font-semibold text-slate-600">Algoritmo *</label>
              <select
                className="input"
                value={form.algorithm}
                onChange={(e) =>
                  setForm({ ...form, algorithm: e.target.value as ForecastAlgorithm })
                }
              >
                <option value="holt_winters">Holt-Winters</option>
                <option value="linear_trend">Linear Trend</option>
                <option value="naive_seasonal">Naive Seasonal</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Frequencia *</label>
              <select
                className="input"
                value={form.frequency}
                onChange={(e) =>
                  setForm({ ...form, frequency: e.target.value as ForecastFrequency })
                }
              >
                <option value="D">Diaria</option>
                <option value="W">Semanal</option>
                <option value="M">Mensal</option>
                <option value="Q">Trimestral</option>
                <option value="Y">Anual</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Agregacao</label>
              <select
                className="input"
                value={form.aggregation}
                onChange={(e) =>
                  setForm({ ...form, aggregation: e.target.value as "sum" | "mean" })
                }
              >
                <option value="sum">sum</option>
                <option value="mean">mean</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-600">
                Horizon (periodos futuros)
              </label>
              <input
                type="number"
                className="input"
                min={1}
                max={120}
                value={form.horizon}
                onChange={(e) => setForm({ ...form, horizon: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">
                Holdout (periodos para backtest)
              </label>
              <input
                type="number"
                className="input"
                min={0}
                max={60}
                value={form.holdout_periods}
                onChange={(e) =>
                  setForm({ ...form, holdout_periods: Number(e.target.value) })
                }
              />
            </div>
          </div>
          <div className="text-[11px] text-slate-500">
            Group-by (forecast por grupo) e parametros avancados podem ser ajustados no editor depois de criar.
          </div>
        </div>
      </Modal>
    </PageContainer>
  );
}
