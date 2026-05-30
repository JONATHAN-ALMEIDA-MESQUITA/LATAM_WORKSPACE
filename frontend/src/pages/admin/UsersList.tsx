/**
 * Admin — Users (Phase 8).
 */

import { useEffect, useState } from "react";
import { UsersAPI, WorkspacesAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type { User, UserCreatePayload, Workspace } from "@/types";

const ROLES = [
  "Platform Admin",
  "Data Developer",
  "Data Analyst",
  "Finance Owner",
  "Operations Owner",
  "LATAM Executive Viewer",
  "Viewer",
  "ML Owner",
];

export default function UsersList() {
  const canManage = !!useAuthStore((s) => s.permissions?.manage_users);
  const [users, setUsers] = useState<User[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<UserCreatePayload>({
    email: "",
    full_name: "",
    role: "Viewer",
    home_workspace: "LATAM",
  });

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [u, w] = await Promise.all([UsersAPI.list(), WorkspacesAPI.listAll()]);
      setUsers(u);
      setWorkspaces(w);
    } catch (e: unknown) {
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar usuários.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (canManage) refresh();
    else setLoading(false);
  }, [canManage]);

  async function saveEdit() {
    if (!editUser) return;
    try {
      await UsersAPI.update(editUser.id, {
        full_name: editUser.full_name,
        role: editUser.role,
        home_workspace: editUser.home_workspace,
        is_active: editUser.is_active,
      });
      setEditUser(null);
      await refresh();
    } catch (e: unknown) {
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Erro ao salvar.",
      );
    }
  }

  async function createUser() {
    try {
      await UsersAPI.create(form);
      setCreateOpen(false);
      setForm({ email: "", full_name: "", role: "Viewer", home_workspace: "LATAM" });
      await refresh();
    } catch (e: unknown) {
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Erro ao criar usuário.",
      );
    }
  }

  if (!canManage) {
    return (
      <PageContainer title="Users" subtitle="Gestão de usuários">
        <EmptyState title="Sem permissão" description="Capability manage_users necessária." />
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Users"
      subtitle="Gerencie perfis, roles e workspaces dos usuários da plataforma."
      actions={
        <Button variant="primary" onClick={() => setCreateOpen(true)}>
          + Novo usuário
        </Button>
      }
    >
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">Carregando...</p>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  <th className="px-4 py-2">Nome</th>
                  <th className="px-4 py-2">Email</th>
                  <th className="px-4 py-2">Role</th>
                  <th className="px-4 py-2">Workspace</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-slate-100">
                    <td className="px-4 py-2 font-medium">{u.full_name}</td>
                    <td className="px-4 py-2 text-slate-600">{u.email}</td>
                    <td className="px-4 py-2">{u.role}</td>
                    <td className="px-4 py-2">{u.home_workspace}</td>
                    <td className="px-4 py-2">
                      <Badge tone={u.is_active ? "success" : "danger"}>
                        {u.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                    <td className="px-4 py-2">
                      <Button variant="secondary" onClick={() => setEditUser({ ...u })}>
                        Editar
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Modal open={!!editUser} onClose={() => setEditUser(null)} title="Editar usuário">
        {editUser && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">{editUser.email}</p>
            <label className="block text-sm">
              Nome
              <input
                className="mt-1 w-full rounded border px-3 py-2"
                value={editUser.full_name}
                onChange={(e) => setEditUser({ ...editUser, full_name: e.target.value })}
              />
            </label>
            <label className="block text-sm">
              Role
              <select
                className="mt-1 w-full rounded border px-3 py-2"
                value={editUser.role}
                onChange={(e) => setEditUser({ ...editUser, role: e.target.value })}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              Home workspace
              <select
                className="mt-1 w-full rounded border px-3 py-2"
                value={editUser.home_workspace}
                onChange={(e) => setEditUser({ ...editUser, home_workspace: e.target.value })}
              >
                {workspaces.map((w) => (
                  <option key={w.id} value={w.name}>
                    {w.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={editUser.is_active}
                onChange={(e) => setEditUser({ ...editUser, is_active: e.target.checked })}
              />
              Usuário ativo
            </label>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setEditUser(null)}>
                Cancelar
              </Button>
              <Button variant="primary" onClick={saveEdit}>
                Salvar
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Novo usuário">
        <div className="space-y-3">
          <label className="block text-sm">
            Email
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            Nome
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </label>
          <label className="block text-sm">
            Role
            <select
              className="mt-1 w-full rounded border px-3 py-2"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Home workspace
            <select
              className="mt-1 w-full rounded border px-3 py-2"
              value={form.home_workspace}
              onChange={(e) => setForm({ ...form, home_workspace: e.target.value })}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.name}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancelar
            </Button>
            <Button variant="primary" onClick={createUser}>
              Criar
            </Button>
          </div>
        </div>
      </Modal>
    </PageContainer>
  );
}
