/**
 * Admin — Permissions matrix (Phase 8).
 */

import { useEffect, useState } from "react";
import { AdminAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAuthStore } from "@/store/authStore";
import type { PermissionsMatrix } from "@/types";

export default function PermissionsMatrix() {
  const canView = !!useAuthStore((s) => s.permissions?.manage_permissions);
  const [matrix, setMatrix] = useState<PermissionsMatrix | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!canView) {
      setLoading(false);
      return;
    }
    AdminAPI.permissionsMatrix()
      .then(setMatrix)
      .catch((e) =>
        setError(
          (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            "Falha ao carregar matriz.",
        ),
      )
      .finally(() => setLoading(false));
  }, [canView]);

  if (!canView) {
    return (
      <PageContainer title="Permissions" subtitle="Matriz RBAC">
        <EmptyState title="Sem permissão" description="Capability manage_permissions necessária." />
      </PageContainer>
    );
  }

  const caps = matrix?.capabilities.filter((c) =>
    filter ? c.toLowerCase().includes(filter.toLowerCase()) : true,
  ) ?? [];

  return (
    <PageContainer
      title="Permissions"
      subtitle="Matriz read-only de roles × capabilities (source of truth no backend)."
    >
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading || !matrix ? (
        <p className="text-sm text-slate-500">Carregando...</p>
      ) : (
        <>
          <div className="mb-4">
            <input
              className="w-full max-w-md rounded border px-3 py-2 text-sm"
              placeholder="Filtrar capabilities..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>

          <Card title="Capabilities por role" bodyClassName="p-0">
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-xs">
                <thead>
                  <tr className="border-b bg-slate-50">
                    <th className="sticky left-0 bg-slate-50 px-3 py-2 font-semibold">Capability</th>
                    {matrix.roles.map((r) => (
                      <th key={r} className="whitespace-nowrap px-2 py-2 font-semibold">
                        {r.replace(" Owner", "").replace(" Platform Admin", " Admin")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {caps.map((cap) => (
                    <tr key={cap} className="border-b border-slate-100">
                      <td className="sticky left-0 bg-white px-3 py-1.5 font-mono">{cap}</td>
                      {matrix.roles.map((role) => (
                        <td key={role} className="px-2 py-1.5 text-center">
                          {matrix.matrix[role]?.includes(cap) ? (
                            <span className="text-emerald-600">✓</span>
                          ) : (
                            <span className="text-slate-300">—</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card title="Workspace access por role">
              <ul className="space-y-2 text-sm">
                {matrix.roles.map((role) => (
                  <li key={role}>
                    <span className="font-medium">{role}:</span>{" "}
                    {matrix.workspace_access[role] === null
                      ? "Todos"
                      : matrix.workspace_access[role]?.join(", ") || "—"}
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Business areas por role">
              <ul className="space-y-2 text-sm">
                {matrix.roles.map((role) => (
                  <li key={role}>
                    <span className="font-medium">{role}:</span>{" "}
                    {matrix.business_areas[role] === null
                      ? "Todas"
                      : matrix.business_areas[role]?.join(", ") || "—"}
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </>
      )}
    </PageContainer>
  );
}
