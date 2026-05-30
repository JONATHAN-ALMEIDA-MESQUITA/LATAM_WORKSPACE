/**
 * Dashboard Builder - constrói dashboards com drag-and-drop usando react-grid-layout.
 *
 * Layout da tela:
 *   - Esquerda (sidebar): lista de dashboards + ação "novo"
 *   - Direita: canvas do dashboard selecionado, com:
 *       * cabeçalho (nome, status, publish actions)
 *       * paleta de widgets (clique adiciona widget vazio)
 *       * grid 12 cols (draggable/resizable) com widgets renderizados via WidgetRenderer
 *       * cada widget tem botões "editar" e "remover"
 *   - Modal de edição de widget (config panel + preview live)
 */

import { useCallback, useEffect, useMemo, useState } from "react";
// v2 do react-grid-layout moveu Responsive/WidthProvider para /legacy.
import { Responsive, WidthProvider } from "react-grid-layout/legacy";
import type { LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

import { DashboardsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { WidgetConfigPanel } from "@/components/widgets/WidgetConfigPanel";
import { WidgetRenderer } from "@/components/widgets/WidgetRenderer";
import { useAuthStore } from "@/store/authStore";
import type {
  Dashboard,
  DashboardSummary,
  Widget,
  WidgetConfig,
  WidgetRenderResult,
  WidgetType,
} from "@/types";

const ResponsiveGrid = WidthProvider(Responsive);

const WIDGET_PALETTE: { type: WidgetType; label: string; icon: string }[] = [
  { type: "kpi_card", label: "KPI", icon: "▢" },
  { type: "bar_chart", label: "Bar", icon: "▣" },
  { type: "line_chart", label: "Line", icon: "📈" },
  { type: "area_chart", label: "Area", icon: "🌄" },
  { type: "pie_chart", label: "Pie", icon: "🥧" },
  { type: "donut_chart", label: "Donut", icon: "🍩" },
  { type: "table", label: "Table", icon: "▦" },
  { type: "text_box", label: "Text", icon: "T" },
];

const STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Draft: "warning",
  "Pending Approval": "info",
  Published: "success",
  Archived: "neutral",
  Deprecated: "danger",
};

const DEFAULT_LAYOUT: Record<WidgetType, { w: number; h: number }> = {
  kpi_card: { w: 3, h: 3 },
  bar_chart: { w: 6, h: 5 },
  line_chart: { w: 6, h: 5 },
  area_chart: { w: 6, h: 5 },
  pie_chart: { w: 4, h: 5 },
  donut_chart: { w: 4, h: 5 },
  table: { w: 12, h: 5 },
  text_box: { w: 6, h: 3 },
};

export default function DashboardBuilder() {
  const permissions = useAuthStore((s) => s.permissions);
  const menu = useAuthStore((s) => s.menu);
  const workspaces = menu?.workspaces ?? ["LATAM"];

  const [list, setList] = useState<DashboardSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Dashboard | null>(null);
  const [renderResults, setRenderResults] = useState<WidgetRenderResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Modais
  const [showCreateDashboard, setShowCreateDashboard] = useState(false);
  const [newName, setNewName] = useState("");
  const [newWorkspace, setNewWorkspace] = useState(workspaces[0] ?? "LATAM");
  const [newArea, setNewArea] = useState("Sales");

  // Widget editor
  const [editingWidget, setEditingWidget] = useState<Widget | null>(null);
  const [editingNew, setEditingNew] = useState<WidgetType | null>(null);
  const [widgetTitle, setWidgetTitle] = useState("");
  const [widgetConfig, setWidgetConfig] = useState<WidgetConfig>({});
  const [widgetPreview, setWidgetPreview] = useState<WidgetRenderResult | null>(null);
  const [widgetSaving, setWidgetSaving] = useState(false);
  const [widgetError, setWidgetError] = useState<string | null>(null);
  const [exportingPdf, setExportingPdf] = useState(false);

  const canEdit = (permissions?.create_dashboard ?? false) && (
    !detail || detail.status === "Draft" || detail.status === "Archived" || (permissions?.publish_any ?? false)
  );

  async function refreshList() {
    setLoading(true);
    setError(null);
    try {
      const items = await DashboardsAPI.list({});
      setList(items);
      if (items.length > 0 && selectedId === null) {
        setSelectedId(items[0].id);
      }
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao listar dashboards.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(id: number) {
    setError(null);
    try {
      const [d, rendered] = await Promise.all([
        DashboardsAPI.get(id),
        DashboardsAPI.render(id).catch(() => [] as WidgetRenderResult[]),
      ]);
      setDetail(d);
      setRenderResults(rendered);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar dashboard.",
      );
    }
  }

  useEffect(() => {
    refreshList();
  }, []);

  useEffect(() => {
    if (selectedId !== null) loadDetail(selectedId);
  }, [selectedId]);

  // ---- Layout drag/resize ----
  const layout: LayoutItem[] = useMemo(
    () =>
      (detail?.widgets ?? []).map((w) => ({
        i: String(w.id),
        x: w.layout.x ?? 0,
        y: w.layout.y ?? 0,
        w: w.layout.w ?? 4,
        h: w.layout.h ?? 3,
        minW: 2,
        minH: 2,
      })),
    [detail],
  );

  const onLayoutChange = useCallback(
    async (next: readonly LayoutItem[]) => {
      if (!detail || !canEdit) return;
      // Atualiza no backend só os widgets que mudaram
      const tasks: Promise<unknown>[] = [];
      for (const l of next) {
        const w = detail.widgets.find((x) => String(x.id) === l.i);
        if (!w) continue;
        if (w.layout.x !== l.x || w.layout.y !== l.y || w.layout.w !== l.w || w.layout.h !== l.h) {
          tasks.push(
            DashboardsAPI.updateWidget(detail.id, w.id, {
              layout: { x: l.x, y: l.y, w: l.w, h: l.h },
            }),
          );
        }
      }
      if (tasks.length > 0) {
        await Promise.all(tasks).catch(() => {});
        await loadDetail(detail.id);
      }
    },
    [detail, canEdit],
  );

  // ---- Criar dashboard ----
  async function handleCreateDashboard() {
    if (!newName.trim()) return;
    try {
      const d = await DashboardsAPI.create({
        name: newName.trim(),
        workspace: newWorkspace,
        business_area: newArea,
      });
      setShowCreateDashboard(false);
      setNewName("");
      await refreshList();
      setSelectedId(d.id);
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao criar dashboard.",
      );
    }
  }

  // ---- Editor de widget ----
  function openCreateWidget(type: WidgetType) {
    if (!detail || !canEdit) return;
    setEditingWidget(null);
    setEditingNew(type);
    setWidgetTitle("");
    setWidgetConfig({});
    setWidgetPreview(null);
    setWidgetError(null);
  }

  function openEditWidget(w: Widget) {
    setEditingWidget(w);
    setEditingNew(null);
    setWidgetTitle(w.title);
    setWidgetConfig({ ...w.config });
    setWidgetPreview(null);
    setWidgetError(null);
  }

  const widgetTypeActive: WidgetType | null = editingWidget
    ? (editingWidget.widget_type as WidgetType)
    : editingNew;

  // Valida campos minimos antes de chamar o backend - mensagens amigaveis
  function validateWidget(): string | null {
    if (!widgetTypeActive) return "Selecione um tipo de widget.";
    if (widgetTypeActive === "text_box") {
      if (!widgetConfig.text_content) return "Adicione o texto do widget.";
      return null;
    }
    if (!widgetConfig.dataset_id) return "Selecione um dataset.";
    if (widgetTypeActive === "table") {
      // colunas vazias = mostra todas (backend resolve)
      return null;
    }
    // KPI / charts precisam de métrica
    if (!widgetConfig.metric_id && !widgetConfig.metric_inline) {
      return "Selecione uma métrica (Existente/Rápida/Fórmula).";
    }
    if (widgetConfig.metric_inline) {
      const cfg = widgetConfig.metric_inline.formula_config as {
        column?: string;
        formula?: string;
      };
      if (
        widgetConfig.metric_inline.formula_type !== "CUSTOM_LIMITED" &&
        !cfg.column
      ) {
        return "Métrica rápida: selecione a coluna.";
      }
      if (
        widgetConfig.metric_inline.formula_type === "CUSTOM_LIMITED" &&
        !cfg.formula
      ) {
        return "Métrica fórmula: digite a expressão DSL (ex: SUM(revenue)).";
      }
    }
    // Charts precisam de dimensão
    if (widgetTypeActive !== "kpi_card" && !widgetConfig.dimension) {
      return "Charts precisam de uma dimensão (groupby).";
    }
    return null;
  }

  async function handlePreviewWidget() {
    if (!widgetTypeActive) return;
    const v = validateWidget();
    if (v) {
      setWidgetError(v);
      return;
    }
    setWidgetError(null);
    try {
      const result = await DashboardsAPI.previewWidget({
        widget_type: widgetTypeActive,
        config: { ...widgetConfig, label: widgetTitle || widgetConfig.label },
      });
      setWidgetPreview(result);
    } catch (err: unknown) {
      setWidgetError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao gerar preview do widget.",
      );
    }
  }

  async function handleSaveWidget() {
    if (!detail || !widgetTypeActive) return;
    setWidgetSaving(true);
    setWidgetError(null);
    try {
      if (editingWidget) {
        await DashboardsAPI.updateWidget(detail.id, editingWidget.id, {
          title: widgetTitle,
          widget_type: widgetTypeActive,
          config: widgetConfig as Record<string, unknown>,
        });
      } else {
        const def = DEFAULT_LAYOUT[widgetTypeActive];
        const maxY = (detail.widgets ?? []).reduce((acc, w) => Math.max(acc, w.layout.y + w.layout.h), 0);
        await DashboardsAPI.createWidget(detail.id, {
          title: widgetTitle || "(sem título)",
          widget_type: widgetTypeActive,
          layout: { x: 0, y: maxY, w: def.w, h: def.h },
          config: widgetConfig as Record<string, unknown>,
        });
      }
      setEditingWidget(null);
      setEditingNew(null);
      await loadDetail(detail.id);
    } catch (err: unknown) {
      setWidgetError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao salvar widget.",
      );
    } finally {
      setWidgetSaving(false);
    }
  }

  async function handleDeleteWidget(w: Widget) {
    if (!detail || !canEdit) return;
    if (!confirm(`Remover widget "${w.title}"?`)) return;
    try {
      await DashboardsAPI.deleteWidget(detail.id, w.id);
      await loadDetail(detail.id);
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao remover widget.",
      );
    }
  }

  // ---- Publish actions ----
  async function publishAction(action: "submit" | "publish" | "archive" | "reject") {
    if (!detail) return;
    try {
      let updated: Dashboard;
      if (action === "submit") updated = await DashboardsAPI.submit(detail.id);
      else if (action === "publish") updated = await DashboardsAPI.publish(detail.id);
      else if (action === "archive") updated = await DashboardsAPI.archive(detail.id);
      else updated = await DashboardsAPI.reject(detail.id);
      setDetail(updated);
      await refreshList();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          `Falha ao executar ${action}.`,
      );
    }
  }

  async function exportPdf() {
    if (!detail) return;
    setExportingPdf(true);
    try {
      await DashboardsAPI.exportPdf(detail.id);
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao exportar PDF.",
      );
    } finally {
      setExportingPdf(false);
    }
  }

  async function handleDeleteDashboard() {
    if (!detail) return;
    if (!confirm(`Remover dashboard "${detail.name}" e todos os widgets?`)) return;
    try {
      await DashboardsAPI.delete(detail.id);
      setSelectedId(null);
      setDetail(null);
      setRenderResults([]);
      await refreshList();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao remover dashboard.",
      );
    }
  }

  return (
    <PageContainer
      title="Dashboard Builder"
      subtitle="Monte dashboards drag-and-drop, configure widgets e envie para aprovação."
      actions={
        permissions?.create_dashboard && (
          <Button onClick={() => setShowCreateDashboard(true)}>+ Novo dashboard</Button>
        )
      }
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        {/* Sidebar - lista de dashboards */}
        <Card className="overflow-hidden">
          <div className="border-b border-slate-100 p-3">
            <div className="text-sm font-semibold text-slate-700">Dashboards</div>
            <div className="text-xs text-slate-500">{list.length} no total</div>
          </div>
          <div className="max-h-[70vh] overflow-y-auto p-2">
            {loading && <div className="px-2 py-3 text-sm text-slate-500">Carregando...</div>}
            {!loading && list.length === 0 && (
              <div className="px-2 py-3 text-sm text-slate-500">Nenhum dashboard ainda.</div>
            )}
            {list.map((d) => (
              <button
                key={d.id}
                onClick={() => setSelectedId(d.id)}
                className={`mb-1 w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                  selectedId === d.id
                    ? "bg-brand-100 text-brand-800"
                    : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                <div className="font-medium">{d.name}</div>
                <div className="mt-0.5 flex items-center gap-2 text-[11px] text-slate-500">
                  <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>{d.status}</Badge>
                  <span>· {d.workspace}</span>
                  <span>· {d.widget_count}w</span>
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* Canvas */}
        <div className="space-y-4">
          {error && (
            <div className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </div>
          )}

          {!detail ? (
            <Card>
              <EmptyState
                title="Nenhum dashboard selecionado"
                description="Selecione um dashboard à esquerda ou crie um novo para começar."
              />
            </Card>
          ) : (
            <>
              {/* Header do dashboard */}
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3 p-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-xl font-bold text-slate-800">{detail.name}</h2>
                      <Badge tone={STATUS_TONE[detail.status] ?? "neutral"}>{detail.status}</Badge>
                    </div>
                    <div className="mt-1 text-sm text-slate-500">
                      {detail.workspace} · {detail.business_area || "(sem área)"} · {detail.widgets.length} widgets
                      · criado por {detail.created_by}
                    </div>
                    {detail.description && (
                      <div className="mt-1 text-sm text-slate-600">{detail.description}</div>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {permissions?.export_dashboard && detail.widgets.length > 0 && (
                      <Button variant="secondary" loading={exportingPdf} onClick={exportPdf}>
                        Exportar PDF
                      </Button>
                    )}
                    {detail.status === "Draft" && permissions?.submit_for_approval && (
                      <Button variant="secondary" onClick={() => publishAction("submit")}>
                        Enviar p/ aprovação
                      </Button>
                    )}
                    {detail.status === "Pending Approval" && (
                      <>
                        <Button variant="ghost" onClick={() => publishAction("reject")}>
                          Rejeitar
                        </Button>
                        <Button variant="primary" onClick={() => publishAction("publish")}>
                          Aprovar e publicar
                        </Button>
                      </>
                    )}
                    {detail.status === "Draft" && permissions?.publish_any && (
                      <Button variant="primary" onClick={() => publishAction("publish")}>
                        Publicar direto
                      </Button>
                    )}
                    {detail.status === "Published" && (
                      <Button variant="ghost" onClick={() => publishAction("archive")}>
                        Arquivar
                      </Button>
                    )}
                    {canEdit && (
                      <Button variant="ghost" onClick={handleDeleteDashboard}>
                        Remover
                      </Button>
                    )}
                  </div>
                </div>
              </Card>

              {/* Paleta de widgets */}
              {canEdit && (
                <Card>
                  <div className="flex flex-wrap items-center gap-2 p-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-500 mr-2">
                      + Adicionar widget:
                    </span>
                    {WIDGET_PALETTE.map((w) => (
                      <button
                        key={w.type}
                        onClick={() => openCreateWidget(w.type)}
                        className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
                      >
                        <span className="mr-1">{w.icon}</span>
                        {w.label}
                      </button>
                    ))}
                  </div>
                </Card>
              )}

              {/* Grid de widgets */}
              {detail.widgets.length === 0 ? (
                <Card>
                  <EmptyState
                    title="Dashboard vazio"
                    description="Use a paleta acima para adicionar o primeiro widget."
                  />
                </Card>
              ) : (
                <div className="rounded-2xl bg-slate-50/50 p-2">
                  <ResponsiveGrid
                    className="layout"
                    layouts={{ lg: layout, md: layout, sm: layout, xs: layout, xxs: layout }}
                    breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                    cols={{ lg: 12, md: 12, sm: 12, xs: 6, xxs: 4 }}
                    rowHeight={50}
                    isDraggable={canEdit}
                    isResizable={canEdit}
                    onLayoutChange={onLayoutChange}
                    draggableHandle=".widget-drag-handle"
                    margin={[10, 10]}
                  >
                    {detail.widgets.map((w) => {
                      const result =
                        renderResults.find((r) => r.widget_id === w.id) ??
                        ({
                          widget_type: w.widget_type,
                          title: w.title,
                          kpi: null,
                          chart: null,
                          table: null,
                          text: null,
                          rows_used: 0,
                          notes: "Aguardando preview...",
                        } as WidgetRenderResult);
                      return (
                        <div key={String(w.id)} className="relative">
                          <div className="widget-drag-handle absolute right-1 top-1 z-10 flex gap-1 rounded bg-white/90 px-1 py-0.5 shadow-sm opacity-0 hover:opacity-100 group-hover:opacity-100 transition-opacity">
                            {canEdit && (
                              <>
                                <button
                                  className="rounded px-1 text-[10px] text-slate-600 hover:bg-slate-100"
                                  onClick={() => openEditWidget(w)}
                                  title="Editar widget"
                                >
                                  ✏️
                                </button>
                                <button
                                  className="rounded px-1 text-[10px] text-rose-600 hover:bg-rose-50"
                                  onClick={() => handleDeleteWidget(w)}
                                  title="Remover widget"
                                >
                                  🗑️
                                </button>
                              </>
                            )}
                          </div>
                          {/* Drag handle invisível no topo do widget */}
                          <div className="widget-drag-handle absolute top-0 left-0 right-0 h-6 z-0 cursor-move" />
                          <div className="h-full">
                            <WidgetRenderer result={result} />
                          </div>
                        </div>
                      );
                    })}
                  </ResponsiveGrid>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Modal criar dashboard */}
      <Modal
        open={showCreateDashboard}
        onClose={() => setShowCreateDashboard(false)}
        title="Novo dashboard"
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowCreateDashboard(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCreateDashboard}>Criar</Button>
          </div>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-slate-600">Nome *</label>
            <input
              className="input"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Ex: Sales LATAM 2026"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-600">Workspace</label>
              <select className="input" value={newWorkspace} onChange={(e) => setNewWorkspace(e.target.value)}>
                {workspaces.map((w) => (
                  <option key={w} value={w}>{w}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-600">Business area</label>
              <select className="input" value={newArea} onChange={(e) => setNewArea(e.target.value)}>
                <option value="">(nenhuma)</option>
                <option>Sales</option>
                <option>Finance</option>
                <option>Operations</option>
                <option>Supplier</option>
                <option>HR</option>
                <option>Executive</option>
              </select>
            </div>
          </div>
        </div>
      </Modal>

      {/* Modal editar widget */}
      <Modal
        open={Boolean(widgetTypeActive)}
        onClose={() => {
          setEditingWidget(null);
          setEditingNew(null);
        }}
        title={editingWidget ? `Editar widget - ${editingWidget.title}` : `Novo widget - ${widgetTypeActive}`}
        size="lg"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => { setEditingWidget(null); setEditingNew(null); }}>
              Cancelar
            </Button>
            <Button variant="secondary" onClick={handlePreviewWidget}>
              Pré-visualizar
            </Button>
            <Button variant="primary" onClick={handleSaveWidget} disabled={widgetSaving}>
              {widgetSaving ? "Salvando..." : editingWidget ? "Atualizar" : "Adicionar"}
            </Button>
          </div>
        }
      >
        {widgetTypeActive && (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <WidgetConfigPanel
                widgetType={widgetTypeActive}
                title={widgetTitle}
                config={widgetConfig}
                onTitleChange={setWidgetTitle}
                onConfigChange={setWidgetConfig}
              />
              {widgetError && (
                <div className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
                  {widgetError}
                </div>
              )}
            </div>
            <div className="min-h-[300px] rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Pré-visualização
              </div>
              {widgetPreview ? (
                <div className="h-[300px]">
                  <WidgetRenderer result={widgetPreview} />
                </div>
              ) : (
                <div className="flex h-[300px] items-center justify-center text-xs text-slate-500">
                  Clique em "Pré-visualizar" para ver o widget renderizado
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </PageContainer>
  );
}
