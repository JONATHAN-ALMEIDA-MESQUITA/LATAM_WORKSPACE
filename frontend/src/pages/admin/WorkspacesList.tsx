/**
 * Admin — Workspaces (Phase 8).
 */

import { useEffect, useState } from "react";
import { WorkspacesAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type { Workspace } from "@/types";

export default function WorkspacesList() {
  const canManage = !!useAuthStore((s) => s.permissions?.manage_workspaces);
  const [items, setItems] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [edit, setEdit] = useState<Workspace | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setItems(await WorkspacesAPI.listAll());
    } catch (e: unknown) {
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar workspaces.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (canManage) refresh();
    else setLoading(false);
  }, [canManage]);

  async function save() {
    if (!edit) return;
    try {
      await WorkspacesAPI.update(edit.id, {
        description: edit.description,
        scope: edit.scope,
      });
      setEdit(null);
      await refresh();
    } catch (e: unknown) {
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Erro ao salvar.",
      );
    }
  }

  if (!canManage) {
    return (
      <PageContainer title="Workspaces" subtitle="Gestão de workspaces">
        <EmptyState title="Sem permissão" description="Capability manage_workspaces necessária." />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Workspaces" subtitle="Configure descrição e escopo dos workspaces regionais e por país.">
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">Carregando...</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {items.map((w) => (
            <Card key={w.id} title={w.name} actions={<Badge tone="info">{w.scope}</Badge>}>
              <p className="text-sm text-slate-600">{w.description || "—"}</p>
              <Button variant="secondary" className="mt-3" onClick={() => setEdit({ ...w })}>
                Editar
              </Button>
            </Card>
          ))}
        </div>
      )}

      <Modal open={!!edit} onClose={() => setEdit(null)} title={`Editar ${edit?.name ?? ""}`}>
        {edit && (
          <div className="space-y-3">
            <label className="block text-sm">
              Descrição
              <textarea
                className="mt-1 w-full rounded border px-3 py-2"
                rows={3}
                value={edit.description}
                onChange={(e) => setEdit({ ...edit, description: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Scope
              <select
                className="mt-1 w-full rounded border px-3 py-2"
                value={edit.scope}
                onChange={(e) => setEdit({ ...edit, scope: e.target.value })}
              >
                <option value="regional">regional</option>
                <option value="country">country</option>
              </select>
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setEdit(null)}>
                Cancelar
              </Button>
              <Button variant="primary" onClick={save}>
                Salvar
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </PageContainer>
  );
}
