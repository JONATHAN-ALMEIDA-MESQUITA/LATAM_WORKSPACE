import { useEffect, useMemo, useState } from "react";
import { DatasetsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAuthStore } from "@/store/authStore";
import type {
  Dataset,
  DatasetColumn,
  DatasetLineage,
  DatasetPreview,
  DatasetQuality,
  DatasetSummary,
} from "@/types";

const STATUS_OPTIONS = ["Draft", "Validated", "Certified", "Deprecated"];
const BUSINESS_AREAS = ["", "Operations", "Finance", "Supplier", "Sales", "LATAM Executive"];
const STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Draft: "warning",
  Validated: "info",
  Certified: "success",
  Deprecated: "danger",
};

export default function DatasetExplorer() {
  const menu = useAuthStore((s) => s.menu);
  const permissions = useAuthStore((s) => s.permissions);

  const [items, setItems] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filtros
  const [fWorkspace, setFWorkspace] = useState<string>("");
  const [fArea, setFArea] = useState<string>("");
  const [fStatus, setFStatus] = useState<string>("");
  const [search, setSearch] = useState("");

  // Detalhe
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Dataset | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [tab, setTab] = useState<"preview" | "columns" | "lineage" | "quality">("preview");
  const [changingStatus, setChangingStatus] = useState(false);
  const [lineage, setLineage] = useState<DatasetLineage | null>(null);
  const [quality, setQuality] = useState<DatasetQuality | null>(null);
  const [loadingLineage, setLoadingLineage] = useState(false);
  const [loadingQuality, setLoadingQuality] = useState(false);
  const [runningQuality, setRunningQuality] = useState(false);

  const workspaces = useMemo(() => ["", ...(menu?.workspaces ?? [])], [menu]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setItems(
        await DatasetsAPI.list({
          workspace: fWorkspace || undefined,
          business_area: fArea || undefined,
          status_filter: fStatus || undefined,
        }),
      );
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar datasets.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [fWorkspace, fArea, fStatus]);

  async function loadDetail(id: number) {
    setSelectedId(id);
    setLoadingDetail(true);
    setDetail(null);
    setPreview(null);
    setLineage(null);
    setQuality(null);
    setTab("preview");
    try {
      const [d, p] = await Promise.all([
        DatasetsAPI.get(id),
        DatasetsAPI.preview(id, 200),
      ]);
      setDetail(d);
      setPreview(p);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao abrir dataset.",
      );
    } finally {
      setLoadingDetail(false);
    }
  }

  async function loadLineage(id: number) {
    if (!permissions?.view_lineage) return;
    setLoadingLineage(true);
    try {
      setLineage(await DatasetsAPI.lineage(id));
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar lineage.",
      );
    } finally {
      setLoadingLineage(false);
    }
  }

  async function loadQuality(id: number) {
    setLoadingQuality(true);
    try {
      setQuality(await DatasetsAPI.quality(id));
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar qualidade.",
      );
    } finally {
      setLoadingQuality(false);
    }
  }

  async function runQualityChecks() {
    if (!detail || !permissions?.run_quality_checks) return;
    setRunningQuality(true);
    try {
      setQuality(await DatasetsAPI.runQuality(detail.id));
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao executar checks.",
      );
    } finally {
      setRunningQuality(false);
    }
  }

  function switchTab(next: "preview" | "columns" | "lineage" | "quality") {
    setTab(next);
    if (!selectedId) return;
    if (next === "lineage" && !lineage) loadLineage(selectedId);
    if (next === "quality" && !quality) loadQuality(selectedId);
  }

  async function changeStatus(newStatus: string) {
    if (!detail) return;
    setChangingStatus(true);
    try {
      const updated = await DatasetsAPI.changeStatus(detail.id, newStatus);
      setDetail(updated);
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao mudar status.",
      );
    } finally {
      setChangingStatus(false);
    }
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter(
      (d) =>
        d.name.toLowerCase().includes(q) ||
        d.description.toLowerCase().includes(q) ||
        d.workspace.toLowerCase().includes(q) ||
        d.business_area.toLowerCase().includes(q),
    );
  }, [items, search]);

  return (
    <PageContainer
      title="Dataset Explorer"
      subtitle="Lista, previews, profiling e certificação dos datasets disponíveis."
    >
      <div className="grid grid-cols-12 gap-5">
        {/* Coluna lista + filtros */}
        <div className="col-span-12 xl:col-span-5">
          <Card title="Filtros" bodyClassName="space-y-3">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar por nome, descrição..."
              className="input"
            />
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <select
                value={fWorkspace}
                onChange={(e) => setFWorkspace(e.target.value)}
                className="input"
              >
                {workspaces.map((w) => (
                  <option key={w} value={w}>
                    {w || "Todos workspaces"}
                  </option>
                ))}
              </select>
              <select
                value={fArea}
                onChange={(e) => setFArea(e.target.value)}
                className="input"
              >
                {BUSINESS_AREAS.map((a) => (
                  <option key={a} value={a}>
                    {a || "Todas áreas"}
                  </option>
                ))}
              </select>
              <select
                value={fStatus}
                onChange={(e) => setFStatus(e.target.value)}
                className="input"
              >
                <option value="">Todos status</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </div>
          </Card>

          <div className="mt-4">
            {error && (
              <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            )}
            {loading ? (
              <div className="space-y-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-20 rounded-xl border border-ink-200 bg-white animate-pulse"
                  />
                ))}
              </div>
            ) : filtered.length === 0 ? (
              <Card>
                <EmptyState
                  title="Nenhum dataset"
                  description="Faça upload ou gere bases sintéticas em Upload Data."
                />
              </Card>
            ) : (
              <ul className="space-y-2">
                {filtered.map((d) => {
                  const active = selectedId === d.id;
                  return (
                    <li key={d.id}>
                      <button
                        onClick={() => loadDetail(d.id)}
                        className={[
                          "w-full text-left rounded-xl border bg-white p-3 transition-all",
                          "hover:border-brand-400 hover:shadow-soft",
                          active
                            ? "border-brand-500 ring-2 ring-brand-100"
                            : "border-ink-200",
                        ].join(" ")}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="font-semibold text-ink-900 truncate">
                              {d.name}
                            </div>
                            <div className="text-xs text-ink-500 mt-0.5 line-clamp-2">
                              {d.description || "Sem descrição."}
                            </div>
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              <Badge tone="neutral">{d.workspace}</Badge>
                              {d.business_area && (
                                <Badge tone="info">{d.business_area}</Badge>
                              )}
                              <Badge tone="brand">{d.source_type}</Badge>
                              <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>
                                {d.status}
                              </Badge>
                            </div>
                          </div>
                          <div className="text-right text-xs text-ink-500 whitespace-nowrap">
                            <div>{d.row_count.toLocaleString("en-US")} linhas</div>
                            <div>{d.column_count} colunas</div>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* Coluna detalhe */}
        <div className="col-span-12 xl:col-span-7">
          {!selectedId ? (
            <Card>
              <EmptyState
                title="Selecione um dataset"
                description="Clique em um item da lista para ver preview e profiling."
                icon={
                  <div className="h-12 w-12 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center text-2xl">
                    ☷
                  </div>
                }
              />
            </Card>
          ) : loadingDetail || !detail ? (
            <Card>
              <div className="h-64 animate-pulse" />
            </Card>
          ) : (
            <Card
              title={detail.name}
              subtitle={detail.description || "Sem descrição."}
              actions={
                <div className="flex items-center gap-2">
                  <Badge tone={STATUS_TONE[detail.status] ?? "neutral"}>
                    {detail.status}
                  </Badge>
                </div>
              }
            >
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-4">
                <Stat label="Workspace" value={detail.workspace} />
                <Stat label="Área" value={detail.business_area || "—"} />
                <Stat label="Linhas" value={detail.row_count.toLocaleString("en-US")} />
                <Stat label="Colunas" value={String(detail.column_count)} />
                <Stat label="Origem" value={detail.source_type} />
              </div>

              <div className="flex items-center gap-2 mb-3">
                <Tab active={tab === "preview"} onClick={() => switchTab("preview")}>
                  Preview
                </Tab>
                <Tab active={tab === "columns"} onClick={() => switchTab("columns")}>
                  Columns & Profile
                </Tab>
                {permissions?.view_lineage && (
                  <Tab active={tab === "lineage"} onClick={() => switchTab("lineage")}>
                    Lineage
                  </Tab>
                )}
                <Tab active={tab === "quality"} onClick={() => switchTab("quality")}>
                  Quality
                </Tab>
                <div className="flex-1" />
                {(permissions?.certify_dataset || detail.created_by) && (
                  <StatusActions
                    current={detail.status}
                    canCertify={permissions?.certify_dataset ?? false}
                    loading={changingStatus}
                    onChange={changeStatus}
                  />
                )}
              </div>

              {tab === "preview" && preview && (
                <DataTable
                  data={preview.rows}
                  columnsHint={preview.columns}
                  pageSize={25}
                  maxHeight="520px"
                />
              )}

              {tab === "columns" && (
                <ProfileTable columns={detail.columns} />
              )}

              {tab === "lineage" && (
                <LineagePanel loading={loadingLineage} lineage={lineage} />
              )}

              {tab === "quality" && (
                <QualityPanel
                  loading={loadingQuality}
                  quality={quality}
                  canRun={permissions?.run_quality_checks ?? false}
                  running={runningQuality}
                  onRun={runQualityChecks}
                />
              )}

              <div className="mt-4 text-xs text-ink-500 flex flex-wrap gap-x-4 gap-y-1">
                <span>Criado por: {detail.created_by}</span>
                <span>Em: {new Date(detail.created_at).toLocaleString("pt-BR")}</span>
                {detail.certified_by && (
                  <span>
                    Certificado por: {detail.certified_by} em{" "}
                    {new Date(detail.certified_at ?? "").toLocaleString("pt-BR")}
                  </span>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>
    </PageContainer>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ink-200 bg-ink-50/40 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-ink-500">{label}</div>
      <div className="mt-0.5 font-semibold text-ink-900 truncate">{value}</div>
    </div>
  );
}

function Tab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={[
        "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
        active ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-ink-100",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function StatusActions({
  current,
  canCertify,
  loading,
  onChange,
}: {
  current: string;
  canCertify: boolean;
  loading: boolean;
  onChange: (newStatus: string) => void;
}) {
  return (
    <div className="flex items-center gap-1">
      {current !== "Draft" && (
        <Button
          variant="ghost"
          onClick={() => onChange("Draft")}
          loading={loading}
          className="text-xs"
        >
          → Draft
        </Button>
      )}
      {current !== "Validated" && (
        <Button
          variant="ghost"
          onClick={() => onChange("Validated")}
          loading={loading}
          className="text-xs"
        >
          → Validated
        </Button>
      )}
      {current !== "Certified" && canCertify && (
        <Button
          onClick={() => onChange("Certified")}
          loading={loading}
          className="text-xs"
        >
          Certificar
        </Button>
      )}
    </div>
  );
}

function ProfileTable({ columns }: { columns: DatasetColumn[] }) {
  return (
    <div className="overflow-auto rounded-xl border border-ink-200 bg-white" style={{ maxHeight: 520 }}>
      <table className="w-full text-sm">
        <thead className="bg-ink-50 sticky top-0">
          <tr className="text-left">
            <th className="px-3 py-2 font-semibold">Coluna</th>
            <th className="px-3 py-2 font-semibold">Tipo</th>
            <th className="px-3 py-2 font-semibold">Nulos</th>
            <th className="px-3 py-2 font-semibold">Distinct</th>
            <th className="px-3 py-2 font-semibold">Min</th>
            <th className="px-3 py-2 font-semibold">Max</th>
            <th className="px-3 py-2 font-semibold">Mean</th>
            <th className="px-3 py-2 font-semibold">Samples</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((c, idx) => (
            <tr
              key={c.id}
              className={idx % 2 === 0 ? "bg-white" : "bg-ink-50/50"}
            >
              <td className="px-3 py-2 font-medium text-ink-900">{c.name}</td>
              <td className="px-3 py-2">
                <Badge tone={dtypeTone(c.dtype)}>{c.dtype}</Badge>
              </td>
              <td className="px-3 py-2 tabular-nums">{c.null_count.toLocaleString("en-US")}</td>
              <td className="px-3 py-2 tabular-nums">{c.distinct_count.toLocaleString("en-US")}</td>
              <td className="px-3 py-2 font-mono text-xs">{c.min_value ?? "—"}</td>
              <td className="px-3 py-2 font-mono text-xs">{c.max_value ?? "—"}</td>
              <td className="px-3 py-2 tabular-nums">
                {c.mean_value != null ? c.mean_value.toLocaleString("en-US", { maximumFractionDigits: 2 }) : "—"}
              </td>
              <td className="px-3 py-2 text-xs text-ink-600">
                {(c.sample_values ?? []).slice(0, 3).map(String).join(", ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function dtypeTone(t: string): "info" | "success" | "warning" | "neutral" {
  if (t === "integer" || t === "float") return "info";
  if (t === "date") return "success";
  if (t === "boolean") return "warning";
  return "neutral";
}

function LineagePanel({
  loading,
  lineage,
}: {
  loading: boolean;
  lineage: DatasetLineage | null;
}) {
  if (loading) {
    return <div className="py-8 text-center text-sm text-ink-500">Carregando lineage...</div>;
  }
  if (!lineage) {
    return (
      <EmptyState
        title="Sem lineage"
        description="Nenhuma dependência registrada para este dataset."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-ink-200 p-3">
          <div className="text-xs font-semibold uppercase text-ink-500 mb-2">Upstream</div>
          {lineage.upstream.length === 0 ? (
            <div className="text-sm text-ink-500">Nenhuma origem.</div>
          ) : (
            <ul className="space-y-2">
              {lineage.upstream.map((n) => (
                <li key={n.id} className="text-sm">
                  <span className="font-medium text-ink-900">{n.name}</span>
                  <span className="text-ink-500"> · {n.source_type} · {n.workspace}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-xl border border-ink-200 p-3">
          <div className="text-xs font-semibold uppercase text-ink-500 mb-2">Downstream</div>
          {lineage.downstream.length === 0 ? (
            <div className="text-sm text-ink-500">Nenhum consumidor.</div>
          ) : (
            <ul className="space-y-2">
              {lineage.downstream.map((n) => (
                <li key={n.id} className="text-sm">
                  <span className="font-medium text-ink-900">{n.name}</span>
                  <span className="text-ink-500"> · {n.source_type} · {n.workspace}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {lineage.edges.length > 0 && (
        <div className="overflow-auto rounded-xl border border-ink-200" style={{ maxHeight: 280 }}>
          <table className="w-full text-sm">
            <thead className="bg-ink-50 sticky top-0">
              <tr className="text-left">
                <th className="px-3 py-2 font-semibold">Relação</th>
                <th className="px-3 py-2 font-semibold">Entidade</th>
                <th className="px-3 py-2 font-semibold">De → Para</th>
              </tr>
            </thead>
            <tbody>
              {lineage.edges.map((e, i) => (
                <tr key={i} className="border-t border-ink-100">
                  <td className="px-3 py-2">{e.relation_type}</td>
                  <td className="px-3 py-2">
                    {e.entity_type}: {e.entity_name}
                  </td>
                  <td className="px-3 py-2 text-ink-500">
                    {e.from_dataset_id ?? "—"} → {e.to_dataset_id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function QualityPanel({
  loading,
  quality,
  canRun,
  running,
  onRun,
}: {
  loading: boolean;
  quality: DatasetQuality | null;
  canRun: boolean;
  running: boolean;
  onRun: () => void;
}) {
  if (loading) {
    return <div className="py-8 text-center text-sm text-ink-500">Carregando qualidade...</div>;
  }

  const scoreTone =
    quality && quality.score >= 90
      ? "success"
      : quality && quality.score >= 70
        ? "warning"
        : "danger";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {quality ? (
            <>
              <span className="text-sm text-ink-600">Score:</span>
              <Badge tone={scoreTone}>{quality.score.toFixed(0)}%</Badge>
              {quality.run_at && (
                <span className="text-xs text-ink-500">
                  Última execução: {new Date(quality.run_at).toLocaleString("pt-BR")}
                </span>
              )}
            </>
          ) : (
            <span className="text-sm text-ink-500">Nenhum relatório ainda.</span>
          )}
        </div>
        {canRun && (
          <Button variant="secondary" loading={running} onClick={onRun}>
            Executar checks
          </Button>
        )}
      </div>
      {quality && quality.checks.length > 0 ? (
        <div className="overflow-auto rounded-xl border border-ink-200" style={{ maxHeight: 420 }}>
          <table className="w-full text-sm">
            <thead className="bg-ink-50 sticky top-0">
              <tr className="text-left">
                <th className="px-3 py-2 font-semibold">Check</th>
                <th className="px-3 py-2 font-semibold">Coluna</th>
                <th className="px-3 py-2 font-semibold">Status</th>
                <th className="px-3 py-2 font-semibold">Mensagem</th>
              </tr>
            </thead>
            <tbody>
              {quality.checks.map((c, i) => (
                <tr key={i} className="border-t border-ink-100">
                  <td className="px-3 py-2 font-medium">{c.name}</td>
                  <td className="px-3 py-2 text-ink-500">{c.column ?? "—"}</td>
                  <td className="px-3 py-2">
                    <Badge tone={c.passed ? "success" : c.severity === "error" ? "danger" : "warning"}>
                      {c.passed ? "OK" : "Falhou"}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-ink-600">{c.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !loading && (
          <EmptyState
            title="Sem checks"
            description="Execute os checks de qualidade para gerar um relatório."
          />
        )
      )}
    </div>
  );
}
