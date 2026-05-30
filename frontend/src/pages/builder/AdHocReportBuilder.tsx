/**
 * Ad-Hoc Report Builder (Phase 7).
 * Dois modos: SQL Editor (avançado) + Visual Builder (amigável).
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { DatasetsAPI, ReportsAPI } from "@/api/client";
import { ReportPreviewTable } from "@/components/report/ReportPreviewTable";
import { VisualReportPanel } from "@/components/report/VisualReportPanel";
import { PageContainer } from "@/components/layout/PageContainer";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type {
  DatasetColumn,
  DatasetSummary,
  ExtraDatasetRef,
  ReportExample,
  ReportPreviewResult,
  SavedReport,
} from "@/types";

type ReportMode = "sql" | "visual";

const DEMO_DIMS = ["client_master", "product_catalog"] as const;
const TABLE_ALIASES: Record<string, string> = {
  sales_latam: "sales",
  client_master: "clients",
  product_catalog: "products",
};

const DEFAULT_SQL = `SELECT s.country, c.tier, SUM(s.revenue) AS total_revenue
FROM sales s
INNER JOIN clients c ON s.client = c.client
GROUP BY s.country, c.tier
ORDER BY total_revenue DESC
LIMIT 20`;

export default function AdHocReportBuilder() {
  const permissions = useAuthStore((s) => s.permissions);
  const workspaces = useAuthStore((s) => s.menu?.workspaces ?? []);
  const canReport = !!permissions?.create_report;

  const [mode, setMode] = useState<ReportMode>("visual");
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [datasetId, setDatasetId] = useState<number | "">("");
  const [extraIds, setExtraIds] = useState<number[]>([]);
  const [columns, setColumns] = useState<DatasetColumn[]>([]);
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [preview, setPreview] = useState<ReportPreviewResult | null>(null);
  const [examples, setExamples] = useState<ReportExample[]>([]);
  const [saved, setSaved] = useState<SavedReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveDesc, setSaveDesc] = useState("");

  const [datasetOpen, setDatasetOpen] = useState(false);
  const [outputName, setOutputName] = useState("");
  const [outputDesc, setOutputDesc] = useState("");
  const [outputWorkspace, setOutputWorkspace] = useState("LATAM");

  const selectedDataset = useMemo(
    () => datasets.find((d) => d.id === datasetId),
    [datasets, datasetId],
  );

  const dimDatasets = useMemo(
    () => datasets.filter((d) => DEMO_DIMS.includes(d.name as (typeof DEMO_DIMS)[number])),
    [datasets],
  );

  const extraRefs: ExtraDatasetRef[] = useMemo(
    () =>
      extraIds.map((id) => {
        const ds = datasets.find((d) => d.id === id);
        return {
          dataset_id: id,
          alias: ds ? TABLE_ALIASES[ds.name] : undefined,
        };
      }),
    [extraIds, datasets],
  );

  const activeTables = useMemo(() => {
    const names: string[] = [];
    if (selectedDataset) {
      names.push(TABLE_ALIASES[selectedDataset.name] ?? "data");
      if (TABLE_ALIASES[selectedDataset.name]) names.push("data");
    }
    for (const id of extraIds) {
      const ds = datasets.find((d) => d.id === id);
      if (ds) names.push(TABLE_ALIASES[ds.name] ?? ds.name);
    }
    return [...new Set(names)];
  }, [selectedDataset, extraIds, datasets]);

  const loadSaved = useCallback(async () => {
    setSaved(await ReportsAPI.listSaved());
  }, []);

  const loadExamples = useCallback(async () => {
    if (!datasetId) {
      setExamples(await ReportsAPI.examples());
      return;
    }
    setExamples(
      await ReportsAPI.examples({
        dataset_id: Number(datasetId),
        extra_dataset_ids: extraIds.join(",") || undefined,
      }),
    );
  }, [datasetId, extraIds]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const dsList = await DatasetsAPI.list();
        setDatasets(dsList.filter((d) => d.row_count > 0));
        await loadSaved();
        const sales = dsList.find((d) => d.name === "sales_latam");
        if (sales) {
          setDatasetId(sales.id);
          const dims = dsList.filter((d) => DEMO_DIMS.includes(d.name as (typeof DEMO_DIMS)[number]));
          setExtraIds(dims.map((d) => d.id));
        } else if (dsList.length > 0) {
          setDatasetId(dsList[0].id);
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Erro ao carregar dados.");
      } finally {
        setLoading(false);
      }
    })();
  }, [loadSaved]);

  useEffect(() => {
    loadExamples().catch(() => undefined);
  }, [loadExamples]);

  useEffect(() => {
    if (!datasetId) {
      setColumns([]);
      return;
    }
    DatasetsAPI.profile(Number(datasetId)).then(setColumns).catch(() => setColumns([]));
  }, [datasetId]);

  function toggleExtra(id: number) {
    setExtraIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
    setPreview(null);
  }

  async function handlePreview() {
    if (!datasetId) {
      setError("Selecione um dataset.");
      return;
    }
    setRunning(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await ReportsAPI.preview({
        dataset_id: Number(datasetId),
        extra_datasets: extraRefs,
        sql,
        limit: 200,
      });
      setPreview(result);
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (e instanceof Error ? e.message : "Erro na query.");
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
      setPreview(null);
    } finally {
      setRunning(false);
    }
  }

  async function handleExport() {
    if (!canReport || !datasetId) return;
    setRunning(true);
    setError(null);
    try {
      await ReportsAPI.exportCsv({
        dataset_id: Number(datasetId),
        extra_datasets: extraRefs,
        sql,
        limit: 10000,
      });
      setSuccess("CSV exportado.");
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao exportar.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setRunning(false);
    }
  }

  async function handleSaveQuery() {
    if (!canReport || !datasetId || !saveName.trim()) return;
    setRunning(true);
    setError(null);
    try {
      await ReportsAPI.createSaved({
        name: saveName.trim(),
        description: saveDesc,
        workspace: selectedDataset?.workspace ?? "LATAM",
        business_area: selectedDataset?.business_area ?? "",
        source_dataset_id: Number(datasetId),
        sql_query: sql,
      });
      setSaveOpen(false);
      setSaveName("");
      setSaveDesc("");
      setSuccess("Query salva.");
      await loadSaved();
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao salvar.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setRunning(false);
    }
  }

  async function handleSaveDataset() {
    if (!canReport || !datasetId || !outputName.trim()) return;
    setRunning(true);
    setError(null);
    try {
      const res = await ReportsAPI.saveDataset({
        dataset_id: Number(datasetId),
        extra_datasets: extraRefs,
        sql,
        output_name: outputName.trim(),
        description: outputDesc,
        workspace: outputWorkspace,
        business_area: selectedDataset?.business_area ?? "",
      });
      setDatasetOpen(false);
      setOutputName("");
      setOutputDesc("");
      setSuccess(`Dataset criado: ${res.name} (${res.row_count} linhas).`);
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao gravar dataset.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setRunning(false);
    }
  }

  async function loadSavedReport(r: SavedReport) {
    setMode("sql");
    setDatasetId(r.source_dataset_id);
    setSql(r.sql_query);
    setError(null);
    setSuccess(`Query "${r.name}" carregada.`);
    setRunning(true);
    try {
      setPreview(await ReportsAPI.runSaved(r.id));
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Erro ao executar query salva.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <PageContainer title="Ad-Hoc Report Builder" subtitle="Relatórios ad hoc sobre datasets">
        <p className="text-sm text-slate-500">Carregando...</p>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Ad-Hoc Report Builder"
      subtitle="Monte relatórios visualmente ou use SQL avançado com joins entre tabelas."
      actions={
        mode === "sql" ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={handlePreview} disabled={running || !datasetId}>
              {running ? "Executando..." : "Executar preview"}
            </Button>
            {canReport && (
              <>
                <Button variant="secondary" onClick={() => setSaveOpen(true)} disabled={!datasetId}>
                  Salvar query
                </Button>
                <Button variant="secondary" onClick={handleExport} disabled={running || !datasetId}>
                  Export CSV
                </Button>
                <Button variant="secondary" onClick={() => setDatasetOpen(true)} disabled={!datasetId}>
                  Salvar como Dataset
                </Button>
              </>
            )}
          </div>
        ) : null
      }
    >
      <div className="mb-4 flex gap-2 border-b border-slate-200">
        <button
          type="button"
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            mode === "visual"
              ? "border-indigo-600 text-indigo-700"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
          onClick={() => setMode("visual")}
        >
          Visual Builder
        </button>
        <button
          type="button"
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            mode === "sql"
              ? "border-indigo-600 text-indigo-700"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
          onClick={() => setMode("sql")}
        >
          SQL Editor
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {success}
        </div>
      )}

      {mode === "visual" ? (
        <div className="space-y-4">
          <VisualReportPanel
            datasets={datasets}
            running={running}
            onRunningChange={setRunning}
            onPreview={setPreview}
            onError={setError}
            onSuccess={setSuccess}
          />
          <ReportPreviewTable preview={preview} />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-3">
            <Card title="Tabela principal">
              <select
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                value={datasetId}
                onChange={(e) => {
                  setDatasetId(e.target.value ? Number(e.target.value) : "");
                  setPreview(null);
                }}
              >
                <option value="">Selecione...</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.row_count} rows)
                  </option>
                ))}
              </select>
              {selectedDataset && (
                <p className="mt-2 text-xs text-slate-500">
                  Alias: <code>{TABLE_ALIASES[selectedDataset.name] ?? "data"}</code>
                  {TABLE_ALIASES[selectedDataset.name] && (
                    <> + <code>data</code></>
                  )}
                </p>
              )}
            </Card>

            {dimDatasets.length > 0 && (
              <Card title="Tabelas para join">
                <p className="mb-2 text-xs text-slate-500">
                  Marque dimensões para habilitar cross-table joins na demo.
                </p>
                <ul className="space-y-2">
                  {dimDatasets.map((d) => (
                    <li key={d.id}>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={extraIds.includes(d.id)}
                          onChange={() => toggleExtra(d.id)}
                        />
                        <span>
                          {d.name}{" "}
                          <code className="text-xs">{TABLE_ALIASES[d.name]}</code>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <Card title="Tabelas ativas">
              <p className="font-mono text-xs text-slate-600">
                {activeTables.length ? activeTables.join(", ") : "—"}
              </p>
            </Card>

            <Card title="Colunas (principal)">
              {columns.length === 0 ? (
                <p className="text-xs text-slate-500">Nenhuma coluna.</p>
              ) : (
                <ul className="max-h-40 space-y-1 overflow-y-auto text-xs">
                  {columns.map((c) => (
                    <li key={c.name}>
                      <span className="font-mono">{c.name}</span>
                      <span className="ml-1 text-slate-400">({c.dtype})</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card title="Templates SQL">
              <ul className="space-y-2">
                {examples.map((ex) => (
                  <li key={ex.label}>
                    <button
                      type="button"
                      className="w-full rounded border border-slate-200 px-2 py-1.5 text-left text-xs hover:bg-slate-50"
                      onClick={() => setSql(ex.sql)}
                    >
                      {ex.label}
                    </button>
                  </li>
                ))}
              </ul>
            </Card>

            <Card title="Queries salvas">
              {saved.length === 0 ? (
                <EmptyState title="Nenhuma query" description="Salve queries para reutilizar." />
              ) : (
                <ul className="space-y-2">
                  {saved.map((r) => (
                    <li key={r.id}>
                      <button
                        type="button"
                        className="w-full rounded border border-slate-200 px-2 py-2 text-left hover:bg-slate-50"
                        onClick={() => loadSavedReport(r)}
                      >
                        <div className="text-sm font-medium">{r.name}</div>
                        <div className="text-xs text-slate-500">
                          {r.source_dataset_name ?? `dataset #${r.source_dataset_id}`}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="space-y-4 lg:col-span-9">
            <Card title="SQL Editor">
              <p className="mb-2 text-xs text-slate-500">
                Apenas SELECT/WITH. Use aliases{" "}
                <code className="rounded bg-slate-100 px-1">sales</code>,{" "}
                <code className="rounded bg-slate-100 px-1">clients</code>,{" "}
                <code className="rounded bg-slate-100 px-1">products</code> para joins.
              </p>
              <textarea
                className="h-52 w-full resize-y rounded border border-slate-300 p-3 font-mono text-sm"
                value={sql}
                onChange={(e) => setSql(e.target.value)}
                spellCheck={false}
              />
            </Card>
            <ReportPreviewTable preview={preview} />
          </div>
        </div>
      )}

      <Modal open={saveOpen} onClose={() => setSaveOpen(false)} title="Salvar query">
        <div className="space-y-3">
          <label className="block text-sm">
            Nome
            <input
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Descrição
            <textarea
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              rows={2}
              value={saveDesc}
              onChange={(e) => setSaveDesc(e.target.value)}
            />
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setSaveOpen(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={handleSaveQuery} disabled={!saveName.trim() || running}>
              Salvar
            </Button>
          </div>
        </div>
      </Modal>

      <Modal open={datasetOpen} onClose={() => setDatasetOpen(false)} title="Salvar como Dataset">
        <div className="space-y-3">
          <label className="block text-sm">
            Nome do dataset
            <input
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={outputName}
              onChange={(e) => setOutputName(e.target.value)}
              placeholder="report_revenue_by_tier"
            />
          </label>
          <label className="block text-sm">
            Descrição
            <textarea
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              rows={2}
              value={outputDesc}
              onChange={(e) => setOutputDesc(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            Workspace
            <select
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2"
              value={outputWorkspace}
              onChange={(e) => setOutputWorkspace(e.target.value)}
            >
              {(workspaces.length ? workspaces : ["LATAM"]).map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setDatasetOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              onClick={handleSaveDataset}
              disabled={!outputName.trim() || running}
            >
              Criar dataset
            </Button>
          </div>
        </div>
      </Modal>
    </PageContainer>
  );
}
