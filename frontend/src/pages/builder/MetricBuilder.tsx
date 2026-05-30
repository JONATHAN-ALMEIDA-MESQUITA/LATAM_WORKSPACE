/**
 * Metric Builder - cria, edita e certifica métricas da camada semântica.
 *
 * Lista métricas existentes (filtros por dataset/workspace/status).
 * Permite criar nova métrica com formulário dinâmico baseado no tipo:
 *   SUM/AVG/COUNT/MIN/MAX  -> column
 *   RATIO                  -> numerator + denominator
 *   VARIATION_*            -> actual + baseline
 *   MTD/YTD/YOY            -> column + date_column
 *   CUSTOM_LIMITED         -> formula (DSL)
 * Antes de salvar, "Pré-visualizar" calcula o valor sob amostra.
 */

import { useEffect, useMemo, useState } from "react";
import { DatasetsAPI, MetricsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type {
  Dataset,
  DatasetColumn,
  DatasetSummary,
  Metric,
  MetricCreatePayload,
  MetricPreviewResult,
} from "@/types";

const FORMULA_TYPES = [
  { value: "SUM", label: "SUM (soma de uma coluna)" },
  { value: "AVERAGE", label: "AVERAGE (média)" },
  { value: "COUNT", label: "COUNT (contagem)" },
  { value: "MIN", label: "MIN (mínimo)" },
  { value: "MAX", label: "MAX (máximo)" },
  { value: "RATIO", label: "RATIO (numerador / denominador)" },
  { value: "VARIATION_ABS", label: "VARIATION_ABS (actual - baseline)" },
  { value: "VARIATION_PCT", label: "VARIATION_PCT ((actual-baseline)/baseline)" },
  { value: "MTD", label: "MTD (mês corrente)" },
  { value: "YTD", label: "YTD (ano corrente até a data)" },
  { value: "YOY", label: "YOY (variação ano contra ano)" },
  { value: "CUSTOM_LIMITED", label: "CUSTOM (DSL: SUM/SUB/DIVIDE/...)" },
];

const OUTPUT_FORMATS = [
  { value: "number", label: "Number" },
  { value: "currency", label: "Currency" },
  { value: "percent", label: "Percent" },
  { value: "integer", label: "Integer" },
];

const STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Draft: "warning",
  Certified: "success",
  Published: "info",
  Deprecated: "danger",
};

const BUSINESS_AREAS = ["", "Sales", "Finance", "Operations", "Supplier", "HR", "Executive"];

interface FormState {
  id?: number;
  name: string;
  description: string;
  dataset_id: number | "";
  workspace: string;
  business_area: string;
  formula_type: string;
  output_format: string;
  decimals: number;
  // configs dinâmicos
  column: string;
  numerator: string;
  denominator: string;
  actual: string;
  baseline: string;
  date_column: string;
  yoy_mode: "percent" | "abs";
  formula: string;
  distinct: boolean;
}

const INITIAL_FORM: FormState = {
  name: "",
  description: "",
  dataset_id: "",
  workspace: "LATAM",
  business_area: "",
  formula_type: "SUM",
  output_format: "number",
  decimals: 2,
  column: "",
  numerator: "",
  denominator: "",
  actual: "actual",
  baseline: "budget",
  date_column: "",
  yoy_mode: "percent",
  formula: "",
  distinct: false,
};

function buildFormulaConfig(f: FormState): Record<string, unknown> {
  switch (f.formula_type) {
    case "SUM":
    case "AVERAGE":
    case "MIN":
    case "MAX":
      return { column: f.column };
    case "COUNT":
      return { column: f.column || undefined, distinct: f.distinct };
    case "RATIO":
      return { numerator: f.numerator, denominator: f.denominator };
    case "VARIATION_ABS":
    case "VARIATION_PCT":
      return { actual: f.actual, baseline: f.baseline };
    case "MTD":
    case "YTD":
      return { column: f.column, date_column: f.date_column };
    case "YOY":
      return { column: f.column, date_column: f.date_column, mode: f.yoy_mode };
    case "CUSTOM_LIMITED":
      return { formula: f.formula };
    default:
      return {};
  }
}

function parseFormulaConfig(metric: Metric): Partial<FormState> {
  const cfg = metric.formula_config || {};
  const get = (k: string, d = "") => (cfg[k] as string) ?? d;
  return {
    column: get("column"),
    numerator: get("numerator"),
    denominator: get("denominator"),
    actual: get("actual", "actual"),
    baseline: get("baseline", "budget"),
    date_column: get("date_column"),
    yoy_mode: ((cfg.mode as string) || "percent") as "percent" | "abs",
    formula: get("formula"),
    distinct: Boolean(cfg.distinct),
  };
}

export default function MetricBuilder() {
  const menu = useAuthStore((s) => s.menu);
  const permissions = useAuthStore((s) => s.permissions);

  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [fDataset, setFDataset] = useState<string>("");
  const [fWorkspace, setFWorkspace] = useState<string>("");
  const [fStatus, setFStatus] = useState<string>("");

  // Form
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [datasetDetail, setDatasetDetail] = useState<Dataset | null>(null);
  const [previewResult, setPreviewResult] = useState<MetricPreviewResult | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const workspaces = useMemo(() => menu?.workspaces ?? ["LATAM"], [menu]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [ds, ms] = await Promise.all([
        DatasetsAPI.list({}),
        MetricsAPI.list({
          dataset_id: fDataset ? Number(fDataset) : undefined,
          workspace: fWorkspace || undefined,
          status: fStatus || undefined,
        }),
      ]);
      setDatasets(ds);
      setMetrics(ms);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar métricas.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [fDataset, fWorkspace, fStatus]);

  // Quando muda o dataset selecionado no form, carrega as colunas
  useEffect(() => {
    setDatasetDetail(null);
    if (form.dataset_id) {
      DatasetsAPI.get(Number(form.dataset_id))
        .then((d) => setDatasetDetail(d))
        .catch(() => setDatasetDetail(null));
    }
  }, [form.dataset_id]);

  function openNewForm() {
    setForm(INITIAL_FORM);
    setPreviewResult(null);
    setFormError(null);
    setShowForm(true);
  }

  function openEditForm(m: Metric) {
    setForm({
      id: m.id,
      name: m.name,
      description: m.description,
      dataset_id: m.dataset_id,
      workspace: m.workspace,
      business_area: m.business_area || "",
      formula_type: m.formula_type,
      output_format: m.output_format,
      decimals: m.decimals,
      column: "",
      numerator: "",
      denominator: "",
      actual: "actual",
      baseline: "budget",
      date_column: "",
      yoy_mode: "percent",
      formula: "",
      distinct: false,
      ...parseFormulaConfig(m),
    });
    setPreviewResult(null);
    setFormError(null);
    setShowForm(true);
  }

  async function handlePreview() {
    if (!form.dataset_id) return;
    setPreviewing(true);
    setFormError(null);
    try {
      const result = await MetricsAPI.preview({
        dataset_id: Number(form.dataset_id),
        formula_type: form.formula_type,
        formula_config: buildFormulaConfig(form),
      });
      setPreviewResult(result);
    } catch (err: unknown) {
      setFormError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao calcular preview.",
      );
    } finally {
      setPreviewing(false);
    }
  }

  async function handleSave() {
    if (!form.dataset_id || !form.name) {
      setFormError("Nome e dataset são obrigatórios.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      const payload: MetricCreatePayload = {
        name: form.name,
        description: form.description,
        dataset_id: Number(form.dataset_id),
        workspace: form.workspace,
        business_area: form.business_area,
        formula_type: form.formula_type,
        formula_config: buildFormulaConfig(form),
        output_format: form.output_format,
        decimals: form.decimals,
      };
      if (form.id) {
        await MetricsAPI.update(form.id, payload);
      } else {
        await MetricsAPI.create(payload);
      }
      setShowForm(false);
      await refresh();
    } catch (err: unknown) {
      setFormError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao salvar.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(m: Metric, newStatus: string) {
    try {
      await MetricsAPI.update(m.id, { status: newStatus });
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao alterar status.",
      );
    }
  }

  async function handleDelete(m: Metric) {
    if (!confirm(`Remover métrica "${m.name}"?`)) return;
    try {
      await MetricsAPI.delete(m.id);
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao remover.",
      );
    }
  }

  const datasetColumns: DatasetColumn[] = datasetDetail?.columns ?? [];
  const numericColumns = datasetColumns.filter((c) =>
    ["integer", "float"].includes(c.dtype),
  );
  const dateColumns = datasetColumns.filter((c) => c.dtype === "date");
  const canCreate = permissions?.create_metric ?? false;

  return (
    <PageContainer
      title="Metric Builder"
      subtitle="Camada semântica reutilizável: defina métricas certificadas para uso em dashboards e relatórios."
      actions={
        canCreate && (
          <Button onClick={openNewForm} variant="primary">
            + Nova métrica
          </Button>
        )
      }
    >
      {/* Filtros */}
      <Card className="mb-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div>
            <label className="text-xs font-semibold text-slate-600">Dataset</label>
            <select className="input" value={fDataset} onChange={(e) => setFDataset(e.target.value)}>
              <option value="">Todos</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Workspace</label>
            <select className="input" value={fWorkspace} onChange={(e) => setFWorkspace(e.target.value)}>
              <option value="">Todos</option>
              {workspaces.map((w) => (
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
              <option>Certified</option>
              <option>Published</option>
              <option>Deprecated</option>
            </select>
          </div>
          <div className="flex items-end">
            <div className="text-xs text-slate-500">
              {metrics.length} métricas listadas
            </div>
          </div>
        </div>
      </Card>

      {error && (
        <div className="mb-4 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {/* Lista */}
      {loading ? (
        <div className="text-sm text-slate-500">Carregando...</div>
      ) : metrics.length === 0 ? (
        <EmptyState
          title="Nenhuma métrica encontrada"
          description="Crie a primeira métrica para começar a montar dashboards."
          action={canCreate ? <Button onClick={openNewForm}>+ Nova métrica</Button> : undefined}
        />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 text-left">Nome</th>
                  <th className="px-3 py-2 text-left">Tipo</th>
                  <th className="px-3 py-2 text-left">Dataset</th>
                  <th className="px-3 py-2 text-left">Workspace</th>
                  <th className="px-3 py-2 text-left">Área</th>
                  <th className="px-3 py-2 text-left">Formato</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((m) => {
                  const datasetName = datasets.find((d) => d.id === m.dataset_id)?.name ?? `#${m.dataset_id}`;
                  return (
                    <tr key={m.id} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-3 py-2">
                        <div className="font-medium text-slate-800">{m.name}</div>
                        <div className="text-xs text-slate-500">{m.description}</div>
                      </td>
                      <td className="px-3 py-2 text-xs">{m.formula_type}</td>
                      <td className="px-3 py-2 text-xs text-slate-600">{datasetName}</td>
                      <td className="px-3 py-2 text-xs">{m.workspace}</td>
                      <td className="px-3 py-2 text-xs">{m.business_area || "—"}</td>
                      <td className="px-3 py-2 text-xs">{m.output_format} / {m.decimals}d</td>
                      <td className="px-3 py-2">
                        <Badge tone={STATUS_TONE[m.status] ?? "neutral"}>{m.status}</Badge>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex flex-wrap justify-end gap-1">
                          {canCreate && (
                            <Button size="sm" variant="secondary" onClick={() => openEditForm(m)}>
                              Editar
                            </Button>
                          )}
                          {permissions?.certify_dataset && m.status === "Draft" && (
                            <Button size="sm" variant="primary" onClick={() => handleStatusChange(m, "Certified")}>
                              Certificar
                            </Button>
                          )}
                          {canCreate && m.status !== "Deprecated" && (
                            <Button size="sm" variant="ghost" onClick={() => handleStatusChange(m, "Deprecated")}>
                              Depreciar
                            </Button>
                          )}
                          {canCreate && (
                            <Button size="sm" variant="ghost" onClick={() => handleDelete(m)}>
                              Remover
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Modal de criação/edição */}
      <Modal
        open={showForm}
        title={form.id ? `Editar métrica - ${form.name}` : "Nova métrica"}
        onClose={() => setShowForm(false)}
        size="lg"
      >
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div>
              <label className="text-xs font-semibold text-slate-600">Nome *</label>
              <input
                className="input"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ex: Revenue (USD)"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Dataset *</label>
              <select
                className="input"
                value={form.dataset_id}
                onChange={(e) => setForm({ ...form, dataset_id: e.target.value ? Number(e.target.value) : "" })}
                disabled={!!form.id}
              >
                <option value="">Selecione...</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-600">Descrição</label>
            <textarea
              className="input min-h-[60px]"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="O que esta métrica representa?"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div>
              <label className="text-xs font-semibold text-slate-600">Workspace</label>
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
            <div>
              <label className="text-xs font-semibold text-slate-600">Área de negócio</label>
              <select
                className="input"
                value={form.business_area}
                onChange={(e) => setForm({ ...form, business_area: e.target.value })}
              >
                {BUSINESS_AREAS.map((b) => (
                  <option key={b} value={b}>
                    {b || "—"}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Tipo de fórmula *</label>
              <select
                className="input"
                value={form.formula_type}
                onChange={(e) => {
                  setForm({ ...form, formula_type: e.target.value });
                  setPreviewResult(null);
                }}
              >
                {FORMULA_TYPES.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Configuração específica por tipo */}
          <Card className="bg-slate-50">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
              Configuração da fórmula
            </div>
            {!form.dataset_id && (
              <div className="text-xs text-amber-700">Selecione um dataset acima para ver as colunas.</div>
            )}
            {form.dataset_id && (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {["SUM", "AVERAGE", "MIN", "MAX"].includes(form.formula_type) && (
                  <div>
                    <label className="text-xs font-semibold text-slate-600">Coluna numérica</label>
                    <select
                      className="input"
                      value={form.column}
                      onChange={(e) => setForm({ ...form, column: e.target.value })}
                    >
                      <option value="">Selecione...</option>
                      {numericColumns.map((c) => (
                        <option key={c.id} value={c.name}>
                          {c.name} ({c.dtype})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {form.formula_type === "COUNT" && (
                  <>
                    <div>
                      <label className="text-xs font-semibold text-slate-600">Coluna (opcional)</label>
                      <select
                        className="input"
                        value={form.column}
                        onChange={(e) => setForm({ ...form, column: e.target.value })}
                      >
                        <option value="">(todas as linhas)</option>
                        {datasetColumns.map((c) => (
                          <option key={c.id} value={c.name}>
                            {c.name} ({c.dtype})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-end">
                      <label className="flex items-center gap-2 text-xs">
                        <input
                          type="checkbox"
                          checked={form.distinct}
                          onChange={(e) => setForm({ ...form, distinct: e.target.checked })}
                        />
                        Distinct count
                      </label>
                    </div>
                  </>
                )}

                {form.formula_type === "RATIO" && (
                  <>
                    <div>
                      <label className="text-xs font-semibold text-slate-600">Numerador</label>
                      <select
                        className="input"
                        value={form.numerator}
                        onChange={(e) => setForm({ ...form, numerator: e.target.value })}
                      >
                        <option value="">Selecione...</option>
                        {numericColumns.map((c) => (
                          <option key={c.id} value={c.name}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-slate-600">Denominador</label>
                      <select
                        className="input"
                        value={form.denominator}
                        onChange={(e) => setForm({ ...form, denominator: e.target.value })}
                      >
                        <option value="">Selecione...</option>
                        {numericColumns.map((c) => (
                          <option key={c.id} value={c.name}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}

                {(form.formula_type === "VARIATION_ABS" || form.formula_type === "VARIATION_PCT") && (
                  <>
                    <div>
                      <label className="text-xs font-semibold text-slate-600">Coluna Actual</label>
                      <select
                        className="input"
                        value={form.actual}
                        onChange={(e) => setForm({ ...form, actual: e.target.value })}
                      >
                        <option value="">Selecione...</option>
                        {numericColumns.map((c) => (
                          <option key={c.id} value={c.name}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-slate-600">Coluna Baseline</label>
                      <select
                        className="input"
                        value={form.baseline}
                        onChange={(e) => setForm({ ...form, baseline: e.target.value })}
                      >
                        <option value="">Selecione...</option>
                        {numericColumns.map((c) => (
                          <option key={c.id} value={c.name}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}

                {["MTD", "YTD", "YOY"].includes(form.formula_type) && (
                  <>
                    <div>
                      <label className="text-xs font-semibold text-slate-600">Coluna a somar</label>
                      <select
                        className="input"
                        value={form.column}
                        onChange={(e) => setForm({ ...form, column: e.target.value })}
                      >
                        <option value="">Selecione...</option>
                        {numericColumns.map((c) => (
                          <option key={c.id} value={c.name}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-slate-600">Coluna de data</label>
                      <select
                        className="input"
                        value={form.date_column}
                        onChange={(e) => setForm({ ...form, date_column: e.target.value })}
                      >
                        <option value="">Selecione...</option>
                        {dateColumns.map((c) => (
                          <option key={c.id} value={c.name}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                    {form.formula_type === "YOY" && (
                      <div>
                        <label className="text-xs font-semibold text-slate-600">Modo YoY</label>
                        <select
                          className="input"
                          value={form.yoy_mode}
                          onChange={(e) => setForm({ ...form, yoy_mode: e.target.value as "percent" | "abs" })}
                        >
                          <option value="percent">Percentual (%)</option>
                          <option value="abs">Absoluto</option>
                        </select>
                      </div>
                    )}
                  </>
                )}

                {form.formula_type === "CUSTOM_LIMITED" && (
                  <div className="md:col-span-2">
                    <label className="text-xs font-semibold text-slate-600">
                      Fórmula DSL (SUM, SUB, ADD, MULT, DIVIDE, COUNT, AVG, MIN, MAX)
                    </label>
                    <input
                      className="input font-mono text-xs"
                      value={form.formula}
                      onChange={(e) => setForm({ ...form, formula: e.target.value })}
                      placeholder="DIVIDE(SUB(SUM(revenue), SUM(cost)), SUM(revenue))"
                    />
                    <div className="mt-1 text-[11px] text-slate-500">
                      Exemplos: <code>SUM(revenue)</code>,{" "}
                      <code>DIVIDE(SUM(margin), SUM(revenue))</code>,{" "}
                      <code>SUB(SUM(actual), SUM(budget))</code>
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <div>
              <label className="text-xs font-semibold text-slate-600">Formato</label>
              <select
                className="input"
                value={form.output_format}
                onChange={(e) => setForm({ ...form, output_format: e.target.value })}
              >
                {OUTPUT_FORMATS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Decimais</label>
              <input
                type="number"
                className="input"
                value={form.decimals}
                min={0}
                max={6}
                onChange={(e) => setForm({ ...form, decimals: Number(e.target.value) })}
              />
            </div>
            <div className="flex items-end">
              <Button
                variant="secondary"
                onClick={handlePreview}
                disabled={previewing || !form.dataset_id}
              >
                {previewing ? "Calculando..." : "Pré-visualizar"}
              </Button>
            </div>
          </div>

          {previewResult && (
            <Card className="bg-emerald-50 border-emerald-200">
              <div className="text-xs uppercase tracking-wide text-emerald-700">Preview</div>
              <div className="mt-1 text-2xl font-bold text-emerald-900">
                {previewResult.formatted}
              </div>
              <div className="text-xs text-emerald-700">
                {previewResult.rows_used.toLocaleString("en-US")} linhas usadas - valor bruto: {previewResult.value ?? "—"}
              </div>
            </Card>
          )}

          {formError && (
            <div className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
              {formError}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" onClick={() => setShowForm(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={handleSave} disabled={saving}>
              {saving ? "Salvando..." : form.id ? "Atualizar" : "Criar métrica"}
            </Button>
          </div>
        </div>
      </Modal>
    </PageContainer>
  );
}
