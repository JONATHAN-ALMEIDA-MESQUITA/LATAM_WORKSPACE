/**
 * Admin — Audit Logs (Phase 8).
 */

import { useEffect, useState } from "react";
import { AdminAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAuthStore } from "@/store/authStore";
import type { AuditLogEntry } from "@/types";

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function AuditLogViewer() {
  const canView = !!useAuthStore((s) => s.permissions?.view_audit_logs);
  const workspaces = useAuthStore((s) => s.menu?.workspaces ?? []);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fEmail, setFEmail] = useState("");
  const [fAction, setFAction] = useState("");
  const [fWorkspace, setFWorkspace] = useState("");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setLogs(
        await AdminAPI.auditLogs({
          user_email: fEmail || undefined,
          action: fAction || undefined,
          workspace: fWorkspace || undefined,
          limit: 300,
        }),
      );
    } catch (e: unknown) {
      setError(
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar audit logs.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (canView) refresh();
    else setLoading(false);
  }, [canView]);

  if (!canView) {
    return (
      <PageContainer title="Audit Logs" subtitle="Trilha de auditoria">
        <EmptyState title="Sem permissão" description="Capability view_audit_logs necessária." />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Audit Logs" subtitle="Trilha de ações importantes na plataforma.">
      <div className="mb-4 flex flex-wrap gap-2">
        <input
          className="rounded border px-3 py-2 text-sm"
          placeholder="Email..."
          value={fEmail}
          onChange={(e) => setFEmail(e.target.value)}
        />
        <input
          className="rounded border px-3 py-2 text-sm"
          placeholder="Action..."
          value={fAction}
          onChange={(e) => setFAction(e.target.value)}
        />
        <select
          className="rounded border px-3 py-2 text-sm"
          value={fWorkspace}
          onChange={(e) => setFWorkspace(e.target.value)}
        >
          <option value="">Todos workspaces</option>
          {workspaces.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
        <Button variant="primary" onClick={refresh}>
          Filtrar
        </Button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">Carregando...</p>
      ) : logs.length === 0 ? (
        <EmptyState title="Nenhum log" description="Execute seed_audit_logs.py para dados demo." />
      ) : (
        <Card bodyClassName="p-0">
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-xs">
              <thead>
                <tr className="border-b bg-slate-50">
                  <th className="px-3 py-2">Timestamp</th>
                  <th className="px-3 py-2">User</th>
                  <th className="px-3 py-2">Action</th>
                  <th className="px-3 py-2">Object</th>
                  <th className="px-3 py-2">Workspace</th>
                  <th className="px-3 py-2">Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-slate-100">
                    <td className="whitespace-nowrap px-3 py-2">{fmtDate(log.timestamp)}</td>
                    <td className="px-3 py-2">{log.user_email}</td>
                    <td className="px-3 py-2">
                      <Badge tone="info">{log.action}</Badge>
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-slate-500">{log.object_type}</span> {log.object_name}
                    </td>
                    <td className="px-3 py-2">{log.workspace || "—"}</td>
                    <td className="max-w-xs truncate px-3 py-2 text-slate-600" title={log.details}>
                      {log.details || "—"}
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
