/**
 * DashboardViewer - renderiza um dashboard inteiro a partir do dashboard_id.
 * Usa react-grid-layout em modo readonly (sem drag/resize), aplicando o layout salvo.
 * Usado pelo Business Portal e por qualquer página que precise exibir um dashboard publicado.
 */

import { useEffect, useMemo, useState } from "react";
// v2 do react-grid-layout moveu Responsive/WidthProvider para /legacy.
import { Responsive, WidthProvider } from "react-grid-layout/legacy";
import type { LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";

import { DashboardsAPI } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { WidgetRenderer } from "@/components/widgets/WidgetRenderer";
import { useAuthStore } from "@/store/authStore";
import type { Dashboard, WidgetRenderResult } from "@/types";

const ResponsiveGrid = WidthProvider(Responsive);

interface Props {
  dashboardId: number;
  showHeader?: boolean;
}

export function DashboardViewer({ dashboardId, showHeader = true }: Props) {
  const permissions = useAuthStore((s) => s.permissions);
  const [detail, setDetail] = useState<Dashboard | null>(null);
  const [results, setResults] = useState<WidgetRenderResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportingPdf, setExportingPdf] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.all([DashboardsAPI.get(dashboardId), DashboardsAPI.render(dashboardId)])
      .then(([d, r]) => {
        if (!alive) return;
        setDetail(d);
        setResults(r);
      })
      .catch((err: unknown) => {
        if (!alive) return;
        setError(
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            "Falha ao carregar dashboard.",
        );
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [dashboardId]);

  const layout: LayoutItem[] = useMemo(
    () =>
      (detail?.widgets ?? []).map((w) => ({
        i: String(w.id),
        x: w.layout.x ?? 0,
        y: w.layout.y ?? 0,
        w: w.layout.w ?? 4,
        h: w.layout.h ?? 3,
        static: true,
      })),
    [detail],
  );

  async function exportPdf() {
    setExportingPdf(true);
    try {
      await DashboardsAPI.exportPdf(dashboardId);
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao exportar PDF.",
      );
    } finally {
      setExportingPdf(false);
    }
  }

  if (loading)
    return <div className="text-sm text-slate-500 py-6 text-center">Carregando dashboard...</div>;

  if (error)
    return (
      <div className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
        {error}
      </div>
    );

  if (!detail) return null;

  if (detail.widgets.length === 0) {
    return (
      <Card>
        <EmptyState
          title="Dashboard sem widgets"
          description="Este dashboard ainda não possui widgets configurados."
        />
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {showHeader && (
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 className="text-xl font-bold text-slate-800">{detail.name}</h2>
            {detail.description && (
              <div className="text-sm text-slate-500">{detail.description}</div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {permissions?.export_dashboard && (
              <Button variant="secondary" loading={exportingPdf} onClick={exportPdf}>
                Exportar PDF
              </Button>
            )}
            <Badge tone="success">{detail.status}</Badge>
            <span className="text-xs text-slate-400">
              {detail.workspace} · {detail.business_area || "—"} · {detail.widgets.length} widgets
            </span>
          </div>
        </div>
      )}
      <div className="rounded-2xl bg-slate-50/40 p-2">
        <ResponsiveGrid
          className="layout"
          layouts={{ lg: layout, md: layout, sm: layout, xs: layout, xxs: layout }}
          breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
          cols={{ lg: 12, md: 12, sm: 12, xs: 6, xxs: 4 }}
          rowHeight={50}
          isDraggable={false}
          isResizable={false}
          margin={[10, 10]}
        >
          {detail.widgets.map((w) => {
            const result =
              results.find((r) => r.widget_id === w.id) ??
              ({
                widget_type: w.widget_type,
                title: w.title,
                kpi: null,
                chart: null,
                table: null,
                text: null,
                rows_used: 0,
                notes: "Sem dados.",
              } as WidgetRenderResult);
            return (
              <div key={String(w.id)} className="h-full">
                <WidgetRenderer result={result} />
              </div>
            );
          })}
        </ResponsiveGrid>
      </div>
    </div>
  );
}
