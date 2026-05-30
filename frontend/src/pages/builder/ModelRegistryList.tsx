/**
 * Model Registry (Phase 9) — catálogo de modelos ML/forecast registrados.
 */

import { useEffect, useMemo, useState } from "react";
import { ForecastsAPI, ModelRegistryAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type { ForecastSummary, RegisteredModel, RegisteredModelCreatePayload } from "@/types";

const STATUS_TONE: Record<string, "neutral" | "warning" | "success" | "info" | "danger"> = {
  Staging: "warning",
  Production: "success",
  Archived: "neutral",
};

export default function ModelRegistryList() {
  const menu = useAuthStore((s) => s.menu);
  const permissions = useAuthStore((s) => s.permissions);

  const [items, setItems] = useState<RegisteredModel[]>([]);
  const [forecasts, setForecasts] = useState<ForecastSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fWorkspace, setFWorkspace] = useState("");
  const [fStatus, setFStatus] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [promotingId, setPromotingId] = useState<number | null>(null);

  const [form, setForm] = useState<RegisteredModelCreatePayload>({
    name: "",
    version: "1.0.0",
    model_type: "forecast",
    workspace: "LATAM",
    business_area: "Sales",
    status: "Staging",
    description: "",
  });

  const workspaces = useMemo(() => ["", ...(menu?.workspaces ?? [])], [menu]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [models, fc] = await Promise.all([
        ModelRegistryAPI.list({
          workspace: fWorkspace || undefined,
          status: fStatus || undefined,
        }),
        ForecastsAPI.list(),
      ]);
      setItems(models);
      setForecasts(fc);
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar model registry.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [fWorkspace, fStatus]);

  async function handleRegister() {
    if (!form.name.trim()) return;
    setSaving(true);
    try {
      await ModelRegistryAPI.register(form);
      setShowCreate(false);
      setForm({
        name: "",
        version: "1.0.0",
        model_type: "forecast",
        workspace: "LATAM",
        business_area: "Sales",
        status: "Staging",
        description: "",
      });
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao registrar modelo.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function promote(id: number) {
    setPromotingId(id);
    try {
      await ModelRegistryAPI.promote(id);
      await refresh();
    } catch (err: unknown) {
      alert(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao promover modelo.",
      );
    } finally {
      setPromotingId(null);
    }
  }

  return (
    <PageContainer
      title="Model Registry"
      subtitle="Catálogo de modelos ML e forecasts registrados para produção."
      actions={
        permissions?.register_model && (
          <Button onClick={() => setShowCreate(true)}>+ Registrar modelo</Button>
        )
      }
    >
      <Card className="mb-4">
        <div className="flex flex-wrap gap-3 p-1">
          <div>
            <label className="text-xs font-semibold text-slate-600">Workspace</label>
            <select
              className="input mt-1 block"
              value={fWorkspace}
              onChange={(e) => setFWorkspace(e.target.value)}
            >
              {workspaces.map((w) => (
                <option key={w || "all"} value={w}>
                  {w || "Todos"}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Status</label>
            <select
              className="input mt-1 block"
              value={fStatus}
              onChange={(e) => setFStatus(e.target.value)}
            >
              <option value="">Todos</option>
              <option value="Staging">Staging</option>
              <option value="Production">Production</option>
              <option value="Archived">Archived</option>
            </select>
          </div>
        </div>
      </Card>

      {error && (
        <div className="mb-4 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-slate-500 py-8 text-center">Carregando...</div>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            title="Nenhum modelo registrado"
            description="Registre um forecast publicado ou cadastre manualmente."
          />
        </Card>
      ) : (
        <div className="space-y-2">
          {items.map((m) => (
            <Card key={m.id}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-800">{m.name}</span>
                    <Badge tone="neutral">v{m.version}</Badge>
                    <Badge tone={STATUS_TONE[m.status] ?? "neutral"}>{m.status}</Badge>
                  </div>
                  <div className="mt-1 text-sm text-slate-500">
                    {m.algorithm || m.model_type} · {m.workspace} · {m.business_area || "—"}
                  </div>
                  {m.description && (
                    <div className="mt-1 text-sm text-slate-600">{m.description}</div>
                  )}
                  <div className="mt-2 text-xs text-slate-400">
                    Registrado por {m.registered_by} em{" "}
                    {new Date(m.registered_at).toLocaleString("pt-BR")}
                    {m.forecast_id != null && ` · forecast #${m.forecast_id}`}
                  </div>
                </div>
                {permissions?.register_model && m.status !== "Production" && (
                  <Button
                    variant="secondary"
                    loading={promotingId === m.id}
                    onClick={() => promote(m.id)}
                  >
                    Promover p/ Production
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={showCreate}
        title="Registrar modelo"
        onClose={() => setShowCreate(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowCreate(false)}>
              Cancelar
            </Button>
            <Button loading={saving} onClick={handleRegister}>
              Registrar
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-sm">
          <div>
            <label className="font-semibold text-slate-600">Nome</label>
            <input
              className="input mt-1 w-full"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="sales_forecast_v2"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="font-semibold text-slate-600">Versão</label>
              <input
                className="input mt-1 w-full"
                value={form.version}
                onChange={(e) => setForm({ ...form, version: e.target.value })}
              />
            </div>
            <div>
              <label className="font-semibold text-slate-600">Workspace</label>
              <select
                className="input mt-1 w-full"
                value={form.workspace}
                onChange={(e) => setForm({ ...form, workspace: e.target.value })}
              >
                {(menu?.workspaces ?? ["LATAM"]).map((w) => (
                  <option key={w} value={w}>
                    {w}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="font-semibold text-slate-600">Forecast vinculado (opcional)</label>
            <select
              className="input mt-1 w-full"
              value={form.forecast_id ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  forecast_id: e.target.value ? Number(e.target.value) : null,
                })
              }
            >
              <option value="">Nenhum</option>
              {forecasts.map((f) => (
                <option key={f.id} value={f.id}>
                  #{f.id} — {f.name} ({f.algorithm})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="font-semibold text-slate-600">Descrição</label>
            <textarea
              className="input mt-1 w-full"
              rows={2}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
        </div>
      </Modal>
    </PageContainer>
  );
}
