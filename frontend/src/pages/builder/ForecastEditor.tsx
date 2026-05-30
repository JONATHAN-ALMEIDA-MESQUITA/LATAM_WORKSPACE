/**
 * ForecastEditor - editor de um forecast (config + train + visualizacao + history).
 *
 * Layout em 3 colunas:
 *   [config (esquerda)] [chart Plotly + metricas (centro)] [runs + actions (direita)]
 *
 * Fluxo:
 *   1. Usuario ajusta config (algoritmo, params, group_by, filtros)
 *   2. Salva (PUT /forecasts/{id})
 *   3. Train (POST /forecasts/{id}/train) -> retorna pontos + metricas
 *   4. Visualiza grafico com IC 95%
 *   5. Publica (POST /forecasts/{id}/publish) -> gera Dataset com output
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { DatasetsAPI, ForecastsAPI } from "@/api/client";
import { ForecastChart } from "@/components/forecast/ForecastChart";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type {
  DatasetColumn,
  DatasetSummary,
  ForecastAlgorithm,
  ForecastDetail,
  ForecastFrequency,
  ForecastMetrics,
  ForecastRun,
  ForecastTrainResponse,
  ForecastUpdatePayload,
} from "@/types";

const ALGORITHM_INFO: Record<
  ForecastAlgorithm,
  { label: string; description: string; params: string[] }
> = {
  naive_seasonal: {
    label: "Naive Seasonal",
    description: "Baseline: media dos ultimos N ciclos do mesmo slot sazonal.",
    params: ["season", "lookback_cycles"],
  },
  linear_trend: {
    label: "Linear Trend",
    description: "Regressao linear sobre trend + dummies sazonais.",
    params: ["season"],
  },
  holt_winters: {
    label: "Holt-Winters",
    description: "Triple exponential smoothing com trend e sazonalidade.",
    params: ["trend", "seasonal", "damped", "season"],
  },
};

const FREQUENCY_OPTIONS: { value: ForecastFrequency; label: string }[] = [
  { value: "D", label: "Diaria" },
  { value: "W", label: "Semanal" },
  { value: "M", label: "Mensal" },
  { value: "Q", label: "Trimestral" },
  { value: "Y", label: "Anual" },
];

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

function fmtMetric(v: number | null | undefined, suffix = ""): string {
  if (v === null || v === undefined) return "—";
  if (suffix === "%") return `${v.toFixed(2)}%`;
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k${suffix}`;
  return `${v.toFixed(2)}${suffix}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

interface MetricsTableProps {
  metrics: Record<string, ForecastMetrics> | null;
}

function MetricsTable({ metrics }: MetricsTableProps) {
  if (!metrics) return <div className="text-xs text-slate-500">Sem metricas. Rode Train.</div>;
  const entries = Object.entries(metrics);
  if (entries.length === 0)
    return <div className="text-xs text-slate-500">Sem metricas calculadas.</div>;

  return (
    <div className="max-h-64 overflow-auto">
      <table className="w-full text-xs">
        <thead className="bg-slate-100 text-slate-700">
          <tr>
            <th className="px-2 py-1 text-left">Grupo</th>
            <th className="px-2 py-1 text-right">MAE</th>
            <th className="px-2 py-1 text-right">RMSE</th>
            <th className="px-2 py-1 text-right">MAPE</th>
            <th className="px-2 py-1 text-right">n_test</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, m]) => (
            <tr key={key} className="border-b border-slate-100">
              <td className="px-2 py-1 font-mono">{key === "__global__" ? "(global)" : key}</td>
              <td className="px-2 py-1 text-right">{fmtMetric(m.mae)}</td>
              <td className="px-2 py-1 text-right">{fmtMetric(m.rmse)}</td>
              <td
                className={`px-2 py-1 text-right ${
                  typeof m.mape === "number" && m.mape < 15
                    ? "text-emerald-700"
                    : typeof m.mape === "number" && m.mape < 30
                      ? "text-amber-700"
                      : "text-rose-700"
                }`}
              >
                {fmtMetric(m.mape, "%")}
              </td>
              <td className="px-2 py-1 text-right">{m.n_test ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ForecastEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const permissions = useAuthStore((s) => s.permissions);
  const canPublish = !!permissions?.publish_forecast || !!permissions?.publish_any;
  const canEdit = !!permissions?.create_forecast;

  const forecastId = Number(id);

  const [forecast, setForecast] = useState<ForecastDetail | null>(null);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [columns, setColumns] = useState<DatasetColumn[]>([]);
  const [trainResult, setTrainResult] = useState<ForecastTrainResponse | null>(null);
  const [runs, setRuns] = useState<ForecastRun[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [training, setTraining] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runsOpen, setRunsOpen] = useState(false);

  // local form state (espelho do forecast pra edicao)
  const [form, setForm] = useState<ForecastUpdatePayload>({});
  const [groupByInput, setGroupByInput] = useState("");
  const [filtersJson, setFiltersJson] = useState("{}");
  const [paramsJson, setParamsJson] = useState("{}");

  const loadAll = useCallback(async () => {
    if (!forecastId) return;
    setLoading(true);
    setError(null);
    try {
      const [f, ds, rs] = await Promise.all([
        ForecastsAPI.get(forecastId),
        DatasetsAPI.list({}),
        ForecastsAPI.runs(forecastId, 20),
      ]);
      setForecast(f);
      setDatasets(ds);
      setRuns(rs);
      setForm({
        name: f.name,
        description: f.description,
        workspace: f.workspace,
        business_area: f.business_area,
        source_dataset_id: f.source_dataset_id,
        target_column: f.target_column,
        date_column: f.date_column,
        frequency: f.frequency,
        group_by: f.group_by,
        aggregation: f.aggregation,
        algorithm: f.algorithm,
        algorithm_params: f.algorithm_params,
        horizon: f.horizon,
        holdout_periods: f.holdout_periods,
        filters: f.filters,
      });
      setGroupByInput((f.group_by ?? []).join(", "));
      setFiltersJson(JSON.stringify(f.filters ?? {}, null, 2));
      setParamsJson(JSON.stringify(f.algorithm_params ?? {}, null, 2));
      try {
        const cols = await DatasetsAPI.profile(f.source_dataset_id);
        setColumns(cols);
      } catch {
        setColumns([]);
      }
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar forecast.",
      );
    } finally {
      setLoading(false);
    }
  }, [forecastId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Quando dataset muda, recarregar colunas
  useEffect(() => {
    if (!form.source_dataset_id) return;
    DatasetsAPI.profile(form.source_dataset_id)
      .then(setColumns)
      .catch(() => setColumns([]));
  }, [form.source_dataset_id]);

  const numericColumns = useMemo(
    () =>
      columns.filter((c) =>
        ["int", "int64", "float", "float64", "number", "numeric"].some((n) =>
          c.dtype.toLowerCase().includes(n),
        ),
      ),
    [columns],
  );

  const dateColumns = useMemo(
    () =>
      columns.filter(
        (c) =>
          c.dtype.toLowerCase().includes("date") ||
          c.dtype.toLowerCase().includes("time") ||
          c.name.toLowerCase().includes("date") ||
          c.name.toLowerCase().includes("dt"),
      ),
    [columns],
  );

  async function handleSave() {
    if (!forecast) return;
    setSaving(true);
    setError(null);
    try {
      let filters: Record<string, unknown> = {};
      let algorithmParams: Record<string, unknown> = {};
      try {
        filters = JSON.parse(filtersJson || "{}");
      } catch {
        setError("filters: JSON invalido.");
        setSaving(false);
        return;
      }
      try {
        algorithmParams = JSON.parse(paramsJson || "{}");
      } catch {
        setError("algorithm_params: JSON invalido.");
        setSaving(false);
        return;
      }
      const groupBy = groupByInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const payload: ForecastUpdatePayload = {
        ...form,
        group_by: groupBy,
        filters,
        algorithm_params: algorithmParams,
      };
      const updated = await ForecastsAPI.update(forecast.id, payload);
      setForecast(updated);
      setForm({
        name: updated.name,
        description: updated.description,
        workspace: updated.workspace,
        business_area: updated.business_area,
        source_dataset_id: updated.source_dataset_id,
        target_column: updated.target_column,
        date_column: updated.date_column,
        frequency: updated.frequency,
        group_by: updated.group_by,
        aggregation: updated.aggregation,
        algorithm: updated.algorithm,
        algorithm_params: updated.algorithm_params,
        horizon: updated.horizon,
        holdout_periods: updated.holdout_periods,
        filters: updated.filters,
      });
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao salvar.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleTrain() {
    if (!forecast) return;
    setTraining(true);
    setError(null);
    setTrainResult(null);
    try {
      const r = await ForecastsAPI.train(forecast.id);
      setTrainResult(r);
      const fresh = await ForecastsAPI.get(forecast.id);
      setForecast(fresh);
      const freshRuns = await ForecastsAPI.runs(forecast.id, 20);
      setRuns(freshRuns);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Falha no treino.";
      setError(`Treino falhou: ${detail}`);
    } finally {
      setTraining(false);
    }
  }

  async function handlePublish() {
    if (!forecast) return;
    if (
      !confirm(
        "Publicar este forecast?\n\nIsso vai re-treinar e gravar o output como Dataset disponivel no Metric/Dashboard Builder.",
      )
    )
      return;
    setPublishing(true);
    try {
      const updated = await ForecastsAPI.publish(forecast.id, "approved from editor");
      setForecast(updated);
      const freshRuns = await ForecastsAPI.runs(forecast.id, 20);
      setRuns(freshRuns);
      alert(`Publicado! Dataset gerado: #${updated.output_dataset_id}`);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Falha ao publicar.";
      alert(`Falha ao publicar: ${detail}`);
    } finally {
      setPublishing(false);
    }
  }

  if (loading) {
    return (
      <PageContainer title="Forecasting Editor">
        <Card>Carregando...</Card>
      </PageContainer>
    );
  }

  if (!forecast) {
    return (
      <PageContainer title="Forecasting Editor">
        <Card>Forecast nao encontrado.</Card>
      </PageContainer>
    );
  }

  const algorithm = (form.algorithm ?? forecast.algorithm) as ForecastAlgorithm;
  const algoInfo = ALGORITHM_INFO[algorithm];

  return (
    <PageContainer
      title={forecast.name}
      subtitle={`Forecasting Studio · ${forecast.workspace}${
        forecast.business_area ? ` / ${forecast.business_area}` : ""
      }`}
      actions={
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => navigate("/builder/forecasts")}>
            ← Voltar
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setRunsOpen(true)}>
            Historico ({runs.length})
          </Button>
          {canEdit && (
            <Button variant="secondary" size="sm" onClick={handleSave} disabled={saving}>
              {saving ? "Salvando..." : "Salvar config"}
            </Button>
          )}
          <Button variant="primary" size="sm" onClick={handleTrain} disabled={training}>
            {training ? "Treinando..." : "Train & Backtest"}
          </Button>
          {canPublish && (
            <Button variant="primary" size="sm" onClick={handlePublish} disabled={publishing}>
              {publishing ? "Publicando..." : "Publicar"}
            </Button>
          )}
        </div>
      }
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone={STATUS_TONE[forecast.status] ?? "neutral"}>{forecast.status}</Badge>
        <Badge tone="info">{algoInfo?.label ?? algorithm}</Badge>
        {forecast.output_dataset_id && (
          <Badge tone="success">Output: dataset #{forecast.output_dataset_id}</Badge>
        )}
        {forecast.last_run_status && (
          <Badge tone={RUN_STATUS_TONE[forecast.last_run_status] ?? "neutral"}>
            Ultima run: {forecast.last_run_status} ({fmtDate(forecast.last_run_at)})
          </Badge>
        )}
      </div>

      {error && (
        <Card className="mb-3 border-rose-200 bg-rose-50 text-sm text-rose-700">{error}</Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr_320px]">
        {/* === Coluna esquerda: configuracao === */}
        <Card>
          <div className="mb-3 text-sm font-semibold text-slate-700">Configuracao</div>
          <div className="space-y-3 text-xs">
            <div>
              <label className="font-semibold text-slate-600">Nome</label>
              <input
                className="input"
                value={form.name ?? ""}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                disabled={!canEdit}
              />
            </div>
            <div>
              <label className="font-semibold text-slate-600">Descricao</label>
              <textarea
                className="input min-h-[50px]"
                value={form.description ?? ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                disabled={!canEdit}
              />
            </div>

            <div>
              <label className="font-semibold text-slate-600">Dataset de origem</label>
              <select
                className="input"
                value={form.source_dataset_id ?? 0}
                onChange={(e) =>
                  setForm({ ...form, source_dataset_id: Number(e.target.value) })
                }
                disabled={!canEdit}
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.workspace})
                  </option>
                ))}
              </select>
              <div className="mt-1 text-[10px] text-slate-500">
                {columns.length} colunas detectadas
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="font-semibold text-slate-600">Coluna alvo</label>
                <select
                  className="input"
                  value={form.target_column ?? ""}
                  onChange={(e) => setForm({ ...form, target_column: e.target.value })}
                  disabled={!canEdit}
                >
                  <option value="">--</option>
                  {(numericColumns.length > 0 ? numericColumns : columns).map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name} ({c.dtype})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-semibold text-slate-600">Coluna data</label>
                <select
                  className="input"
                  value={form.date_column ?? ""}
                  onChange={(e) => setForm({ ...form, date_column: e.target.value })}
                  disabled={!canEdit}
                >
                  <option value="">--</option>
                  {(dateColumns.length > 0 ? dateColumns : columns).map((c) => (
                    <option key={c.name} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="font-semibold text-slate-600">Frequencia</label>
                <select
                  className="input"
                  value={form.frequency ?? "M"}
                  onChange={(e) =>
                    setForm({ ...form, frequency: e.target.value as ForecastFrequency })
                  }
                  disabled={!canEdit}
                >
                  {FREQUENCY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-semibold text-slate-600">Agregacao</label>
                <select
                  className="input"
                  value={form.aggregation ?? "sum"}
                  onChange={(e) =>
                    setForm({ ...form, aggregation: e.target.value as "sum" | "mean" })
                  }
                  disabled={!canEdit}
                >
                  <option value="sum">sum</option>
                  <option value="mean">mean</option>
                </select>
              </div>
            </div>

            <div>
              <label className="font-semibold text-slate-600">
                Group by (forecast por grupo)
              </label>
              <input
                className="input font-mono text-xs"
                value={groupByInput}
                onChange={(e) => setGroupByInput(e.target.value)}
                placeholder="ex: country, category"
                disabled={!canEdit}
              />
              <div className="mt-1 text-[10px] text-slate-500">
                Colunas separadas por virgula. Vazio = serie unica global.
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="font-semibold text-slate-600">Horizon</label>
                <input
                  type="number"
                  className="input"
                  min={1}
                  max={120}
                  value={form.horizon ?? 12}
                  onChange={(e) => setForm({ ...form, horizon: Number(e.target.value) })}
                  disabled={!canEdit}
                />
              </div>
              <div>
                <label className="font-semibold text-slate-600">Holdout</label>
                <input
                  type="number"
                  className="input"
                  min={0}
                  max={60}
                  value={form.holdout_periods ?? 6}
                  onChange={(e) =>
                    setForm({ ...form, holdout_periods: Number(e.target.value) })
                  }
                  disabled={!canEdit}
                />
              </div>
            </div>

            <div className="rounded border border-brand-200 bg-brand-50 p-2">
              <div className="mb-1 font-semibold text-slate-700">Algoritmo</div>
              <select
                className="input mb-2"
                value={form.algorithm ?? "holt_winters"}
                onChange={(e) =>
                  setForm({ ...form, algorithm: e.target.value as ForecastAlgorithm })
                }
                disabled={!canEdit}
              >
                <option value="holt_winters">Holt-Winters</option>
                <option value="linear_trend">Linear Trend</option>
                <option value="naive_seasonal">Naive Seasonal</option>
              </select>
              {algoInfo && (
                <div className="mb-2 text-[10px] text-slate-600">{algoInfo.description}</div>
              )}
              <div>
                <label className="font-semibold text-slate-600">algorithm_params (JSON)</label>
                <textarea
                  className="input min-h-[60px] font-mono text-[11px]"
                  value={paramsJson}
                  onChange={(e) => setParamsJson(e.target.value)}
                  disabled={!canEdit}
                  placeholder='{"trend":"add","seasonal":"add","damped":false}'
                />
                {algoInfo && (
                  <div className="mt-1 text-[10px] text-slate-500">
                    Parametros validos: {algoInfo.params.join(", ")}
                  </div>
                )}
              </div>
            </div>

            <div>
              <label className="font-semibold text-slate-600">Filtros (JSON)</label>
              <textarea
                className="input min-h-[40px] font-mono text-[11px]"
                value={filtersJson}
                onChange={(e) => setFiltersJson(e.target.value)}
                disabled={!canEdit}
                placeholder='{"country": "Brazil"} ou {"country": ["Brazil","Chile"]}'
              />
            </div>
          </div>
        </Card>

        {/* === Coluna central: chart + metricas === */}
        <Card>
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-semibold text-slate-700">
              Visualizacao {trainResult ? `(${trainResult.groups_count} serie(s))` : ""}
            </div>
            {trainResult && (
              <div className="text-xs text-slate-500">
                rows_in: {trainResult.rows_in} · rows_forecast: {trainResult.rows_forecast}
              </div>
            )}
          </div>
          {trainResult ? (
            <ForecastChart points={trainResult.points} height={460} />
          ) : (
            <div className="flex h-[420px] items-center justify-center rounded border border-dashed border-slate-300 text-sm text-slate-500">
              <div className="text-center">
                <div className="mb-2">Nenhum treino executado ainda.</div>
                <Button variant="primary" size="sm" onClick={handleTrain} disabled={training}>
                  {training ? "Treinando..." : "Train & Backtest"}
                </Button>
              </div>
            </div>
          )}
        </Card>

        {/* === Coluna direita: metricas + acoes === */}
        <Card>
          <div className="mb-3 text-sm font-semibold text-slate-700">
            Metricas (backtest no holdout)
          </div>
          <MetricsTable metrics={trainResult?.metrics ?? forecast.last_metrics} />

          <div className="mt-4 border-t border-slate-200 pt-3 text-xs">
            <div className="mb-1 font-semibold text-slate-600">Como interpretar:</div>
            <ul className="space-y-1 text-slate-600">
              <li>
                <strong>MAE</strong>: erro absoluto medio (mesma unidade do alvo).
              </li>
              <li>
                <strong>RMSE</strong>: penaliza erros grandes.
              </li>
              <li>
                <strong>MAPE</strong>: erro percentual. &lt;15% bom · 15-30% ok · &gt;30% ruim.
              </li>
            </ul>
          </div>

          {trainResult && trainResult.points.length > 0 && (
            <div className="mt-4 border-t border-slate-200 pt-3 text-xs">
              <div className="mb-1 font-semibold text-slate-600">Resumo do output</div>
              <div className="text-slate-600">
                <div>Grupos: {trainResult.groups_count}</div>
                <div>Periodos historicos (somados): {trainResult.rows_in}</div>
                <div>Periodos previstos: {trainResult.rows_forecast}</div>
              </div>
            </div>
          )}

          <div className="mt-4 border-t border-slate-200 pt-3 text-xs">
            <div className="mb-1 font-semibold text-slate-600">Audit</div>
            <div className="text-slate-600">
              <div>Criado por: {forecast.created_by}</div>
              <div>Em: {fmtDate(forecast.created_at)}</div>
              {forecast.published_by && (
                <div>
                  Publicado por: {forecast.published_by} em {fmtDate(forecast.published_at)}
                </div>
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* Modal de history */}
      <Modal
        open={runsOpen}
        title="Historico de execucoes"
        onClose={() => setRunsOpen(false)}
        footer={
          <Button variant="secondary" onClick={() => setRunsOpen(false)}>
            Fechar
          </Button>
        }
      >
        {runs.length === 0 ? (
          <div className="text-sm text-slate-500">Nenhuma execucao registrada.</div>
        ) : (
          <div className="max-h-[480px] overflow-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-100 text-slate-700">
                <tr>
                  <th className="px-2 py-1 text-left">ID</th>
                  <th className="px-2 py-1 text-left">Status</th>
                  <th className="px-2 py-1 text-left">Inicio</th>
                  <th className="px-2 py-1 text-right">Duracao</th>
                  <th className="px-2 py-1 text-right">Rows in</th>
                  <th className="px-2 py-1 text-right">Grupos</th>
                  <th className="px-2 py-1 text-right">Output DS</th>
                  <th className="px-2 py-1 text-left">Trigger</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100">
                    <td className="px-2 py-1 font-mono">{r.id}</td>
                    <td className="px-2 py-1">
                      <Badge tone={RUN_STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge>
                    </td>
                    <td className="px-2 py-1">{fmtDate(r.started_at)}</td>
                    <td className="px-2 py-1 text-right">
                      {r.duration_ms ? `${r.duration_ms}ms` : "—"}
                    </td>
                    <td className="px-2 py-1 text-right">{r.rows_in ?? "—"}</td>
                    <td className="px-2 py-1 text-right">{r.groups_count ?? "—"}</td>
                    <td className="px-2 py-1 text-right">{r.output_dataset_id ?? "—"}</td>
                    <td className="px-2 py-1 text-[10px]">{r.triggered_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {runs.some((r) => r.error_message) && (
              <div className="mt-3 rounded border border-rose-200 bg-rose-50 p-2 text-[11px] text-rose-700">
                <div className="font-semibold mb-1">Erros recentes:</div>
                {runs
                  .filter((r) => r.error_message)
                  .slice(0, 3)
                  .map((r) => (
                    <div key={r.id} className="mt-1">
                      <strong>Run #{r.id}</strong>: {r.error_message}
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}
      </Modal>
    </PageContainer>
  );
}
