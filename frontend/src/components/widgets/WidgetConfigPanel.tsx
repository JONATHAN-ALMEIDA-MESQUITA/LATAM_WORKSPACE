/**
 * Painel de configuração de widget - usado pelo Dashboard Builder.
 *
 * Recebe a config atual e dispara onChange ao alterar. O parent (DashboardBuilder)
 * decide quando rodar o preview e quando salvar (atualizar/criar widget).
 */

import { useEffect, useMemo, useState } from "react";
import { DatasetsAPI, MetricsAPI } from "@/api/client";
import { Card } from "@/components/ui/Card";
import type {
  Dataset,
  DatasetSummary,
  Metric,
  WidgetConfig,
  WidgetType,
} from "@/types";

type MetricMode = "existing" | "quick" | "formula";

const QUICK_AGGS = [
  { value: "SUM", label: "Soma (SUM)" },
  { value: "AVERAGE", label: "Média (AVG)" },
  { value: "COUNT", label: "Contagem (COUNT)" },
  { value: "MIN", label: "Mínimo (MIN)" },
  { value: "MAX", label: "Máximo (MAX)" },
];

const OUTPUT_FORMATS = [
  { value: "number", label: "Número" },
  { value: "currency", label: "Moeda ($)" },
  { value: "percent", label: "Porcentagem (%)" },
  { value: "integer", label: "Inteiro" },
];

interface Props {
  widgetType: WidgetType;
  title: string;
  config: WidgetConfig;
  onTitleChange: (v: string) => void;
  onConfigChange: (cfg: WidgetConfig) => void;
}

const TIME_GRAINS = [
  { value: "", label: "(usar valor original)" },
  { value: "day", label: "Dia" },
  { value: "week", label: "Semana" },
  { value: "month", label: "Mês" },
  { value: "quarter", label: "Trimestre" },
  { value: "year", label: "Ano" },
];

export function WidgetConfigPanel({
  widgetType,
  title,
  config,
  onTitleChange,
  onConfigChange,
}: Props) {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [datasetDetail, setDatasetDetail] = useState<Dataset | null>(null);
  const [metrics, setMetrics] = useState<Metric[]>([]);

  useEffect(() => {
    DatasetsAPI.list({}).then(setDatasets).catch(() => setDatasets([]));
  }, []);

  useEffect(() => {
    if (!config.dataset_id) {
      setDatasetDetail(null);
      setMetrics([]);
      return;
    }
    Promise.all([
      DatasetsAPI.get(config.dataset_id),
      MetricsAPI.list({ dataset_id: config.dataset_id }),
    ])
      .then(([d, ms]) => {
        setDatasetDetail(d);
        setMetrics(ms);
      })
      .catch(() => {
        setDatasetDetail(null);
        setMetrics([]);
      });
  }, [config.dataset_id]);

  const datasetColumns = datasetDetail?.columns ?? [];

  const dateColumns = useMemo(
    () => datasetColumns.filter((c) => c.dtype === "date"),
    [datasetColumns],
  );

  function update(partial: Partial<WidgetConfig>) {
    onConfigChange({ ...config, ...partial });
  }

  // ----- Filtros simples (key=value chips) -----
  const filterEntries = Object.entries(config.filters ?? {});
  const [draftFilterCol, setDraftFilterCol] = useState("");
  const [draftFilterVal, setDraftFilterVal] = useState("");

  function addFilter() {
    if (!draftFilterCol || !draftFilterVal) return;
    update({
      filters: { ...(config.filters ?? {}), [draftFilterCol]: draftFilterVal },
    });
    setDraftFilterCol("");
    setDraftFilterVal("");
  }
  function removeFilter(col: string) {
    const next = { ...(config.filters ?? {}) };
    delete next[col];
    update({ filters: next });
  }

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs font-semibold text-slate-600">Título do widget</label>
        <input
          className="input"
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="Ex: Receita YTD"
        />
      </div>

      {/* TEXT BOX - configuração simples */}
      {widgetType === "text_box" ? (
        <div>
          <label className="text-xs font-semibold text-slate-600">
            Texto (use **negrito** para destaque)
          </label>
          <textarea
            className="input min-h-[140px]"
            value={(config.text_content as string) ?? ""}
            onChange={(e) => update({ text_content: e.target.value })}
            placeholder="Insight ou comentário executivo..."
          />
        </div>
      ) : (
        <>
          <div>
            <label className="text-xs font-semibold text-slate-600">Dataset *</label>
            <select
              className="input"
              value={config.dataset_id ?? ""}
              onChange={(e) =>
                update({
                  dataset_id: e.target.value ? Number(e.target.value) : undefined,
                  metric_id: undefined,
                  metric_inline: undefined,
                  dimension: undefined,
                  filters: {},
                })
              }
            >
              <option value="">Selecione...</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.workspace})
                </option>
              ))}
            </select>
          </div>

          {widgetType !== "table" && config.dataset_id && (
            <MetricSelector
              config={config}
              metrics={metrics}
              numericColumns={datasetColumns.filter((c) =>
                ["integer", "float"].includes(c.dtype),
              )}
              onChange={update}
            />
          )}

          {/* KPI tem label customizável */}
          {widgetType === "kpi_card" && (
            <div>
              <label className="text-xs font-semibold text-slate-600">Label do KPI (sobrescreve o nome da métrica)</label>
              <input
                className="input"
                value={(config.label as string) ?? ""}
                onChange={(e) => update({ label: e.target.value })}
                placeholder="Ex: Revenue YTD"
              />
            </div>
          )}

          {/* Charts precisam de dimensão + time_grain */}
          {["bar_chart", "line_chart", "area_chart", "pie_chart", "donut_chart"].includes(widgetType) && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div>
                <label className="text-xs font-semibold text-slate-600">Dimensão *</label>
                <select
                  className="input"
                  value={config.dimension ?? ""}
                  onChange={(e) => update({ dimension: e.target.value })}
                  disabled={!config.dataset_id}
                >
                  <option value="">Selecione...</option>
                  {datasetColumns.map((c) => (
                    <option key={c.id} value={c.name}>
                      {c.name} ({c.dtype})
                    </option>
                  ))}
                </select>
              </div>

              {config.dimension && dateColumns.some((c) => c.name === config.dimension) && (
                <div>
                  <label className="text-xs font-semibold text-slate-600">Granularidade temporal</label>
                  <select
                    className="input"
                    value={config.time_grain ?? ""}
                    onChange={(e) =>
                      update({ time_grain: (e.target.value || undefined) as WidgetConfig["time_grain"] })
                    }
                  >
                    {TIME_GRAINS.map((g) => (
                      <option key={g.value} value={g.value}>{g.label}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="text-xs font-semibold text-slate-600">Ordenação</label>
                <select
                  className="input"
                  value={config.sort ?? "desc"}
                  onChange={(e) => update({ sort: e.target.value as "asc" | "desc" })}
                >
                  <option value="desc">Decrescente</option>
                  <option value="asc">Crescente</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-600">Limit (Top N)</label>
                <input
                  type="number"
                  className="input"
                  value={config.limit ?? 50}
                  min={1}
                  max={500}
                  onChange={(e) => update({ limit: Number(e.target.value) })}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-600">Ordenar por</label>
                <select
                  className="input"
                  value={config.sort_by ?? "value"}
                  onChange={(e) => update({ sort_by: e.target.value })}
                >
                  <option value="value">Valor da métrica</option>
                  {config.dimension && <option value={config.dimension}>{config.dimension}</option>}
                </select>
              </div>
            </div>
          )}

          {/* Tables precisam de colunas + sort */}
          {widgetType === "table" && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-600">Colunas a exibir</label>
                <div className="mt-1 grid grid-cols-2 gap-1 rounded border border-slate-200 p-2 md:grid-cols-4">
                  {datasetColumns.map((c) => {
                    const checked = (config.columns ?? []).includes(c.name);
                    return (
                      <label key={c.id} className="flex items-center gap-1 text-xs">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            const set = new Set(config.columns ?? []);
                            if (e.target.checked) set.add(c.name);
                            else set.delete(c.name);
                            update({ columns: Array.from(set) });
                          }}
                        />
                        {c.name}
                      </label>
                    );
                  })}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-600">Ordenar por</label>
                  <select
                    className="input"
                    value={config.sort_by ?? ""}
                    onChange={(e) => update({ sort_by: e.target.value })}
                  >
                    <option value="">(sem ordem)</option>
                    {datasetColumns.map((c) => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-600">Direção</label>
                  <select
                    className="input"
                    value={config.sort ?? "asc"}
                    onChange={(e) => update({ sort: e.target.value as "asc" | "desc" })}
                  >
                    <option value="asc">Crescente</option>
                    <option value="desc">Decrescente</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-600">Limit</label>
                  <input
                    type="number"
                    className="input"
                    value={config.limit ?? 100}
                    min={1}
                    onChange={(e) => update({ limit: Number(e.target.value) })}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Filtros: chips key=value */}
          {config.dataset_id && (
            <Card className="bg-slate-50">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Filtros (aplicados antes do cálculo)
              </div>
              <div className="space-y-2">
                {filterEntries.length === 0 && (
                  <div className="text-xs text-slate-500">Nenhum filtro definido.</div>
                )}
                {filterEntries.map(([col, val]) => (
                  <div key={col} className="flex items-center gap-2 rounded bg-white px-2 py-1 text-xs">
                    <span className="font-semibold">{col}</span>
                    <span>=</span>
                    <span>{Array.isArray(val) ? (val as string[]).join(", ") : String(val)}</span>
                    <button
                      type="button"
                      className="ml-auto text-rose-600 hover:underline"
                      onClick={() => removeFilter(col)}
                    >
                      remover
                    </button>
                  </div>
                ))}
                <div className="flex gap-2">
                  <select
                    className="input"
                    value={draftFilterCol}
                    onChange={(e) => setDraftFilterCol(e.target.value)}
                  >
                    <option value="">Coluna...</option>
                    {datasetColumns.map((c) => (
                      <option key={c.id} value={c.name}>{c.name}</option>
                    ))}
                  </select>
                  <input
                    className="input"
                    placeholder="valor exato (ex: Brazil)"
                    value={draftFilterVal}
                    onChange={(e) => setDraftFilterVal(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn-secondary text-xs"
                    onClick={addFilter}
                  >
                    Adicionar
                  </button>
                </div>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// MetricSelector - escolhe entre 3 modos: métrica salva / rápida / fórmula DSL
// ---------------------------------------------------------------------------

interface MetricSelectorProps {
  config: WidgetConfig;
  metrics: Metric[];
  numericColumns: { id: number; name: string; dtype: string }[];
  onChange: (partial: Partial<WidgetConfig>) => void;
}

function detectMode(config: WidgetConfig): MetricMode {
  if (config.metric_id) return "existing";
  if (config.metric_inline?.formula_type === "CUSTOM_LIMITED") return "formula";
  if (config.metric_inline) return "quick";
  return "existing";
}

function MetricSelector({ config, metrics, numericColumns, onChange }: MetricSelectorProps) {
  const [mode, setMode] = useState<MetricMode>(detectMode(config));
  const inline = config.metric_inline;

  function switchMode(newMode: MetricMode) {
    setMode(newMode);
    // Limpa o estado oposto ao trocar de modo
    if (newMode === "existing") {
      onChange({ metric_inline: undefined });
    } else {
      onChange({ metric_id: undefined });
    }
  }

  function updateInline(partial: Record<string, unknown>) {
    onChange({
      metric_inline: {
        formula_type: inline?.formula_type ?? "SUM",
        formula_config: inline?.formula_config ?? {},
        output_format: inline?.output_format ?? "number",
        decimals: inline?.decimals ?? 2,
        name: inline?.name ?? "Quick metric",
        ...partial,
      },
    });
  }

  return (
    <Card className="bg-slate-50">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Métrica *
        </div>
        <div className="flex gap-1 rounded-lg bg-white p-0.5 text-xs">
          {(["existing", "quick", "formula"] as MetricMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => switchMode(m)}
              className={`rounded px-2 py-1 ${
                mode === m
                  ? "bg-brand-600 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {m === "existing" ? "Existente" : m === "quick" ? "Rápida" : "Fórmula"}
            </button>
          ))}
        </div>
      </div>

      {/* Modo: existente */}
      {mode === "existing" && (
        <>
          {metrics.length === 0 ? (
            <div className="text-xs text-amber-700">
              Nenhuma métrica cadastrada para este dataset. Use "Rápida" ou "Fórmula", ou crie uma no Metric Builder.
            </div>
          ) : (
            <select
              className="input"
              value={config.metric_id ?? ""}
              onChange={(e) =>
                onChange({ metric_id: e.target.value ? Number(e.target.value) : undefined })
              }
            >
              <option value="">Selecione uma métrica...</option>
              {metrics.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} — {m.formula_type} ({m.status})
                </option>
              ))}
            </select>
          )}
        </>
      )}

      {/* Modo: rápida (column + agg) */}
      {mode === "quick" && (
        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
          <div className="md:col-span-2">
            <label className="text-[10px] uppercase tracking-wide text-slate-500">Agregação</label>
            <select
              className="input"
              value={(inline?.formula_type as string) ?? "SUM"}
              onChange={(e) =>
                updateInline({
                  formula_type: e.target.value,
                  formula_config: {
                    ...(inline?.formula_config ?? {}),
                  },
                })
              }
            >
              {QUICK_AGGS.map((a) => (
                <option key={a.value} value={a.value}>{a.label}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="text-[10px] uppercase tracking-wide text-slate-500">Coluna</label>
            <select
              className="input"
              value={(inline?.formula_config as { column?: string })?.column ?? ""}
              onChange={(e) =>
                updateInline({
                  formula_config: { column: e.target.value },
                  name: `${inline?.formula_type ?? "SUM"}(${e.target.value})`,
                })
              }
            >
              <option value="">Selecione...</option>
              {numericColumns.map((c) => (
                <option key={c.id} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="text-[10px] uppercase tracking-wide text-slate-500">Formato</label>
            <select
              className="input"
              value={inline?.output_format ?? "number"}
              onChange={(e) => updateInline({ output_format: e.target.value })}
            >
              {OUTPUT_FORMATS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className="text-[10px] uppercase tracking-wide text-slate-500">Decimais</label>
            <input
              type="number"
              className="input"
              min={0}
              max={6}
              value={inline?.decimals ?? 2}
              onChange={(e) => updateInline({ decimals: Number(e.target.value) })}
            />
          </div>
        </div>
      )}

      {/* Modo: fórmula DSL */}
      {mode === "formula" && (
        <div className="space-y-2">
          <input
            className="input font-mono text-xs"
            placeholder="Ex: DIVIDE(SUB(SUM(revenue), SUM(cost)), SUM(revenue))"
            value={(inline?.formula_config as { formula?: string })?.formula ?? ""}
            onChange={(e) =>
              updateInline({
                formula_type: "CUSTOM_LIMITED",
                formula_config: { formula: e.target.value },
                name: "Custom",
              })
            }
          />
          <div className="grid grid-cols-2 gap-2">
            <select
              className="input"
              value={inline?.output_format ?? "number"}
              onChange={(e) => updateInline({ output_format: e.target.value })}
            >
              {OUTPUT_FORMATS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <input
              type="number"
              className="input"
              min={0}
              max={6}
              value={inline?.decimals ?? 2}
              onChange={(e) => updateInline({ decimals: Number(e.target.value) })}
            />
          </div>
          <div className="text-[11px] text-slate-500">
            Funções: SUM, AVG, MIN, MAX, COUNT, ADD, SUB, MULT, DIVIDE.
            Exemplo de margem: <code>DIVIDE(SUB(SUM(revenue), SUM(cost)), SUM(revenue))</code>
          </div>
        </div>
      )}
    </Card>
  );
}
