import { useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Link } from "react-router-dom";
import { DatasetsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { useAuthStore } from "@/store/authStore";
import type { Dataset, SampleCatalogItem } from "@/types";

const BUSINESS_AREAS = [
  "Operations",
  "Finance",
  "Supplier",
  "Sales",
  "LATAM Executive",
];

export default function UploadData() {
  const menu = useAuthStore((s) => s.menu);
  const permissions = useAuthStore((s) => s.permissions);

  const [file, setFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [description, setDescription] = useState("");
  const [workspace, setWorkspace] = useState(menu?.workspaces?.[0] ?? "LATAM");
  const [businessArea, setBusinessArea] = useState("Sales");

  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Dataset | null>(null);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);

  const [samples, setSamples] = useState<SampleCatalogItem[]>([]);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generatingOne, setGeneratingOne] = useState<string | null>(null);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      "text/csv": [".csv"],
      "application/vnd.ms-excel": [".xls"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    },
    multiple: false,
    onDrop: (accepted) => {
      const f = accepted[0];
      if (!f) return;
      setFile(f);
      setError(null);
      if (!datasetName) {
        const base = f.name.replace(/\.[^.]+$/, "");
        setDatasetName(base);
      }
    },
  });

  useEffect(() => {
    DatasetsAPI.listSamples().then(setSamples).catch(() => setSamples([]));
  }, []);

  useEffect(() => {
    if (menu?.workspaces?.length && !menu.workspaces.includes(workspace)) {
      setWorkspace(menu.workspaces[0]);
    }
  }, [menu, workspace]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setProgress(0);
    setError(null);
    setResult(null);
    setPreviewRows([]);
    try {
      const ds = await DatasetsAPI.upload(file, {
        dataset_name: datasetName.trim() || file.name,
        description,
        workspace,
        business_area: businessArea,
        onProgress: (pct) => setProgress(pct),
      });
      setResult(ds);
      const prev = await DatasetsAPI.preview(ds.id, 20);
      setPreviewRows(prev.rows);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha no upload.",
      );
    } finally {
      setUploading(false);
    }
  }

  async function handleGenerateAll() {
    setGeneratingAll(true);
    try {
      await DatasetsAPI.generateAllSamples(false);
    } finally {
      setGeneratingAll(false);
    }
  }

  async function handleGenerateOne(name: string) {
    setGeneratingOne(name);
    try {
      await DatasetsAPI.generateSample(name);
    } finally {
      setGeneratingOne(null);
    }
  }

  const canUpload = permissions?.upload_dataset ?? false;

  return (
    <PageContainer
      title="Upload Data"
      subtitle="Carregue CSV/XLSX ou gere bases sintéticas para usar na plataforma."
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-5">
          {!canUpload && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              Seu perfil não tem permissão de <code>upload_dataset</code>.
            </div>
          )}

          <Card title="Arquivo" subtitle="Drag-and-drop ou clique para selecionar.">
            <div
              {...getRootProps()}
              className={[
                "rounded-xl border-2 border-dashed px-6 py-10 text-center cursor-pointer transition-colors",
                isDragActive
                  ? "border-brand-500 bg-brand-50"
                  : "border-ink-300 hover:border-brand-400 hover:bg-ink-50",
              ].join(" ")}
            >
              <input {...getInputProps()} />
              <div className="text-3xl mb-2">⬆</div>
              {file ? (
                <div>
                  <div className="font-medium text-ink-900">{file.name}</div>
                  <div className="text-xs text-ink-500 mt-1">
                    {(file.size / 1024).toFixed(1)} KB · clique ou arraste outro para trocar
                  </div>
                </div>
              ) : (
                <>
                  <div className="font-medium text-ink-900">
                    {isDragActive ? "Solte o arquivo aqui" : "Solte um CSV ou XLSX"}
                  </div>
                  <div className="text-xs text-ink-500 mt-1">
                    Até 50 MB. Apenas arquivos tabulares.
                  </div>
                </>
              )}
            </div>

            <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs font-medium text-ink-700">
                  Nome do dataset *
                </span>
                <input
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  className="input mt-1"
                  placeholder="Como aparecerá no catálogo"
                />
              </label>
              <label className="block">
                <span className="text-xs font-medium text-ink-700">Workspace</span>
                <select
                  value={workspace}
                  onChange={(e) => setWorkspace(e.target.value)}
                  className="input mt-1"
                >
                  {(menu?.workspaces ?? ["LATAM"]).map((w) => (
                    <option key={w}>{w}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs font-medium text-ink-700">Área de negócio</span>
                <select
                  value={businessArea}
                  onChange={(e) => setBusinessArea(e.target.value)}
                  className="input mt-1"
                >
                  {BUSINESS_AREAS.map((b) => (
                    <option key={b}>{b}</option>
                  ))}
                </select>
              </label>
              <label className="block sm:col-span-2">
                <span className="text-xs font-medium text-ink-700">Descrição</span>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="input mt-1 min-h-[60px]"
                />
              </label>
            </div>

            {error && (
              <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            )}

            {uploading && (
              <div className="mt-4">
                <div className="h-2 w-full bg-ink-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-500 transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="mt-1 text-xs text-ink-500">{progress}%</div>
              </div>
            )}

            <div className="mt-4 flex justify-end">
              <Button
                onClick={handleUpload}
                loading={uploading}
                disabled={!file || !datasetName.trim() || !canUpload}
              >
                Carregar dataset
              </Button>
            </div>
          </Card>

          {result && (
            <Card
              title="Resultado do upload"
              subtitle="Dataset criado e perfilado pelo Pandas no backend."
            >
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-sm">
                <Stat label="Linhas" value={result.row_count.toLocaleString("en-US")} />
                <Stat label="Colunas" value={String(result.column_count)} />
                <Stat label="Workspace" value={result.workspace} />
                <Stat label="Status">
                  <Badge tone="warning">{result.status}</Badge>
                </Stat>
              </div>

              <div className="mb-4">
                <div className="text-xs font-semibold text-ink-700 mb-2">
                  Profiling de colunas
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {result.columns.slice(0, 12).map((c) => (
                    <div
                      key={c.id}
                      className="border border-ink-200 rounded-lg p-2 text-xs bg-white"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-ink-900 truncate">{c.name}</span>
                        <Badge tone={dtypeTone(c.dtype)}>{c.dtype}</Badge>
                      </div>
                      <div className="mt-1 text-ink-500">
                        nulls: {c.null_count} · distinct: {c.distinct_count}
                      </div>
                    </div>
                  ))}
                </div>
                {result.columns.length > 12 && (
                  <div className="mt-2 text-xs text-ink-500">
                    + {result.columns.length - 12} colunas. Veja em Dataset Explorer.
                  </div>
                )}
              </div>

              <div>
                <div className="text-xs font-semibold text-ink-700 mb-2">
                  Preview (20 linhas)
                </div>
                <DataTable
                  data={previewRows}
                  enableSearch={false}
                  pageSize={10}
                  maxHeight="320px"
                />
              </div>

              <div className="mt-4 text-right">
                <Link
                  to="/builder/dataset-explorer"
                  className="text-sm text-brand-700 hover:underline"
                >
                  Abrir no Dataset Explorer →
                </Link>
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-5">
          <Card
            title="Bases sintéticas"
            subtitle="Gere dados realistas para popular a demo sem precisar de arquivos."
            actions={
              <Button
                variant="secondary"
                onClick={handleGenerateAll}
                loading={generatingAll}
                disabled={!canUpload}
                className="text-xs"
              >
                Gerar todas
              </Button>
            }
          >
            <ul className="space-y-2">
              {samples.map((s) => (
                <li
                  key={s.name}
                  className="border border-ink-200 rounded-lg p-3 flex items-start justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-ink-900 text-sm truncate">
                      {s.name}
                    </div>
                    <div className="text-xs text-ink-500 mt-0.5">{s.description}</div>
                    <div className="mt-1 flex gap-1.5 flex-wrap">
                      <Badge tone="info">{s.business_area}</Badge>
                      <Badge tone="neutral">{s.workspace}</Badge>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    onClick={() => handleGenerateOne(s.name)}
                    loading={generatingOne === s.name}
                    disabled={!canUpload}
                    className="text-xs whitespace-nowrap"
                  >
                    Gerar
                  </Button>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}

function Stat({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-ink-200 bg-ink-50/40 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-0.5 font-semibold text-ink-900">{value ?? children}</div>
    </div>
  );
}

function dtypeTone(t: string): "info" | "success" | "warning" | "neutral" | "brand" {
  if (t === "integer" || t === "float") return "info";
  if (t === "date") return "success";
  if (t === "boolean") return "warning";
  return "neutral";
}
