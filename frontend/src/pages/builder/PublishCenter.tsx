/**
 * Publish Center - fila de aprovação e gestão do ciclo de vida dos dashboards.
 *
 * Exibe três abas:
 *   - Pendentes de aprovação (Pending Approval) - owner/admin podem aprovar/rejeitar
 *   - Rascunhos (Draft) - lista para acompanhamento
 *   - Publicados (Published) - histórico, com opção de arquivar
 */

import { useEffect, useMemo, useState } from "react";
import { DashboardsAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAuthStore } from "@/store/authStore";
import type { DashboardSummary } from "@/types";

const STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Draft: "warning",
  "Pending Approval": "info",
  Published: "success",
  Archived: "neutral",
  Deprecated: "danger",
};

type Tab = "pending" | "draft" | "published";

export default function PublishCenter() {
  const permissions = useAuthStore((s) => s.permissions);
  const [items, setItems] = useState<DashboardSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("pending");

  const counts = useMemo(() => {
    return {
      pending: items.filter((d) => d.status === "Pending Approval").length,
      draft: items.filter((d) => d.status === "Draft").length,
      published: items.filter((d) => d.status === "Published").length,
    };
  }, [items]);

  const visible = useMemo(() => {
    const status =
      tab === "pending" ? "Pending Approval" : tab === "draft" ? "Draft" : "Published";
    return items.filter((d) => d.status === status);
  }, [items, tab]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      // pegamos todos pra usar contadores
      const all = await DashboardsAPI.list({});
      setItems(all);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar dashboards.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function act(d: DashboardSummary, action: "publish" | "reject" | "archive" | "submit") {
    try {
      if (action === "publish") await DashboardsAPI.publish(d.id);
      else if (action === "reject") await DashboardsAPI.reject(d.id);
      else if (action === "archive") await DashboardsAPI.archive(d.id);
      else await DashboardsAPI.submit(d.id);
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          `Falha ao executar ${action}.`,
      );
    }
  }

  function canPublish(d: DashboardSummary): boolean {
    if (permissions?.publish_any) return true;
    const area = (d.business_area || "").toLowerCase();
    if (area === "finance" && permissions?.publish_finance) return true;
    if (area === "operations" && permissions?.publish_operations) return true;
    return false;
  }

  return (
    <PageContainer
      title="Publish Center"
      subtitle="Fila de aprovação e governança de dashboards: publique, rejeite ou arquive."
    >
      {/* Tabs */}
      <div className="mb-4 flex gap-2">
        <button
          className={`rounded-md px-3 py-1.5 text-sm ${
            tab === "pending"
              ? "bg-brand-600 text-white"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
          onClick={() => setTab("pending")}
        >
          Pendentes ({counts.pending})
        </button>
        <button
          className={`rounded-md px-3 py-1.5 text-sm ${
            tab === "draft"
              ? "bg-brand-600 text-white"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
          onClick={() => setTab("draft")}
        >
          Rascunhos ({counts.draft})
        </button>
        <button
          className={`rounded-md px-3 py-1.5 text-sm ${
            tab === "published"
              ? "bg-brand-600 text-white"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
          onClick={() => setTab("published")}
        >
          Publicados ({counts.published})
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-slate-500">Carregando...</div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            title="Nada por aqui"
            description={
              tab === "pending"
                ? "Não há dashboards aguardando aprovação."
                : tab === "draft"
                  ? "Não há rascunhos no momento."
                  : "Nenhum dashboard publicado."
            }
          />
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2 text-left">Dashboard</th>
                  <th className="px-3 py-2 text-left">Workspace</th>
                  <th className="px-3 py-2 text-left">Área</th>
                  <th className="px-3 py-2 text-left">Widgets</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-left">Criado por</th>
                  <th className="px-3 py-2 text-left">Atualizado em</th>
                  <th className="px-3 py-2 text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((d) => (
                  <tr key={d.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-800">{d.name}</div>
                      <div className="text-xs text-slate-500">{d.description}</div>
                    </td>
                    <td className="px-3 py-2 text-xs">{d.workspace}</td>
                    <td className="px-3 py-2 text-xs">{d.business_area || "—"}</td>
                    <td className="px-3 py-2 text-xs">{d.widget_count}</td>
                    <td className="px-3 py-2">
                      <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>{d.status}</Badge>
                    </td>
                    <td className="px-3 py-2 text-xs">{d.created_by}</td>
                    <td className="px-3 py-2 text-xs text-slate-500">
                      {new Date(d.updated_at).toLocaleString("pt-BR")}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex flex-wrap justify-end gap-1">
                        {tab === "pending" && canPublish(d) && (
                          <>
                            <Button size="sm" variant="primary" onClick={() => act(d, "publish")}>
                              Aprovar e publicar
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => act(d, "reject")}>
                              Rejeitar
                            </Button>
                          </>
                        )}
                        {tab === "draft" && permissions?.submit_for_approval && (
                          <Button size="sm" variant="secondary" onClick={() => act(d, "submit")}>
                            Enviar p/ aprovação
                          </Button>
                        )}
                        {tab === "draft" && canPublish(d) && (
                          <Button size="sm" variant="primary" onClick={() => act(d, "publish")}>
                            Publicar
                          </Button>
                        )}
                        {tab === "published" && canPublish(d) && (
                          <Button size="sm" variant="ghost" onClick={() => act(d, "archive")}>
                            Arquivar
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </PageContainer>
  );
}
