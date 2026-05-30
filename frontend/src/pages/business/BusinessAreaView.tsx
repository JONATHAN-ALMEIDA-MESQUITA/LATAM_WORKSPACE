/**
 * Página única do Business Portal - serve as 5 rotas:
 *   - /business/operations
 *   - /business/finance
 *   - /business/supplier
 *   - /business/sales
 *   - /business/latam-executive
 *
 * Lista dashboards publicados da área de negócio + permite filtrar por workspace.
 * Ao clicar, expande inline o DashboardViewer com o dashboard renderizado.
 */

import { useEffect, useMemo, useState } from "react";
import { DashboardsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { DashboardViewer } from "@/components/widgets/DashboardViewer";
import { useAuthStore } from "@/store/authStore";
import type { DashboardSummary } from "@/types";

interface Props {
  /** Filtro de business_area no backend. Empty = sem filtro (usado em LATAM Executive). */
  businessArea: string;
  title: string;
  subtitle?: string;
  /** Se true, ignora o businessArea no filtro e mostra tudo que o user tem acesso. */
  allowAllAreas?: boolean;
}

export default function BusinessAreaView({
  businessArea,
  title,
  subtitle,
  allowAllAreas = false,
}: Props) {
  const menu = useAuthStore((s) => s.menu);
  const [items, setItems] = useState<DashboardSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [workspaceFilter, setWorkspaceFilter] = useState<string>("");

  const workspaces = useMemo(() => ["", ...(menu?.workspaces ?? [])], [menu]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (!allowAllAreas && businessArea) params.business_area = businessArea;
      if (workspaceFilter) params.workspace = workspaceFilter;
      const list = await DashboardsAPI.listPublished(params);
      setItems(list);
      if (list.length > 0 && selectedId === null) {
        setSelectedId(list[0].id);
      } else if (list.length === 0) {
        setSelectedId(null);
      }
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar dashboards publicados.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [businessArea, workspaceFilter, allowAllAreas]);

  return (
    <PageContainer
      title={title}
      subtitle={subtitle ?? `Dashboards publicados ${businessArea ? `(${businessArea})` : ""}`}
    >
      {error && (
        <div className="mb-4 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        {/* Sidebar */}
        <Card className="overflow-hidden">
          <div className="border-b border-slate-100 p-3 space-y-2">
            <div className="text-sm font-semibold text-slate-700">Dashboards</div>
            <div className="text-xs text-slate-500">{items.length} disponíveis</div>
            <div>
              <label className="text-[10px] uppercase tracking-wide text-slate-500">Workspace</label>
              <select
                className="input text-xs"
                value={workspaceFilter}
                onChange={(e) => setWorkspaceFilter(e.target.value)}
              >
                {workspaces.map((w) => (
                  <option key={w} value={w}>
                    {w || "Todos"}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="max-h-[70vh] overflow-y-auto p-2">
            {loading && <div className="px-2 py-3 text-sm text-slate-500">Carregando...</div>}
            {!loading && items.length === 0 && (
              <div className="px-2 py-3 text-sm text-slate-500">Nenhum dashboard.</div>
            )}
            {items.map((d) => (
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
                  <Badge tone="success">{d.status}</Badge>
                  <span>· {d.workspace}</span>
                  <span>· {d.widget_count}w</span>
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* Viewer */}
        <div>
          {selectedId !== null ? (
            <DashboardViewer dashboardId={selectedId} />
          ) : (
            <Card>
              <EmptyState
                title="Nenhum dashboard selecionado"
                description={
                  items.length > 0
                    ? "Selecione um dashboard à esquerda para visualizá-lo."
                    : "Não há dashboards publicados para esta área no momento."
                }
              />
            </Card>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
