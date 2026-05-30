import { useEffect, useMemo, useState } from "react";
import { DataSourcesAPI } from "@/api/client";
import { PageContainer } from "@/components/layout/PageContainer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type {
  DataSource,
  DataSourceCreatePayload,
  DatabaseType,
  TestConnectionResult,
} from "@/types";

const DB_TYPES: DatabaseType[] = [
  "PostgreSQL",
  "SQL Server",
  "MySQL",
  "SQLite",
  "DuckDB",
];

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  Active: "success",
  "Pending Test": "warning",
  Error: "danger",
  Inactive: "neutral",
};

const initialPayload: DataSourceCreatePayload = {
  connection_name: "",
  database_type: "PostgreSQL",
  host: "",
  port: 5432,
  database_name: "",
  username: "",
  password: "",
  schema: "",
  workspace: "LATAM",
  notes: "",
};

export default function DataSources() {
  const permissions = useAuthStore((s) => s.permissions);
  const menu = useAuthStore((s) => s.menu);

  const [items, setItems] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DataSourceCreatePayload>(initialPayload);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [testingId, setTestingId] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<
    Record<number, TestConnectionResult | undefined>
  >({});

  const canCreate = permissions?.create_data_source ?? false;
  const workspaces = useMemo(() => menu?.workspaces ?? ["LATAM"], [menu]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setItems(await DataSourcesAPI.list());
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao carregar conexões.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function openModal() {
    setDraft({ ...initialPayload, workspace: workspaces[0] ?? "LATAM" });
    setCreateError(null);
    setOpen(true);
  }

  async function submit() {
    setCreating(true);
    setCreateError(null);
    try {
      await DataSourcesAPI.create(draft);
      setOpen(false);
      await refresh();
    } catch (err: unknown) {
      setCreateError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao criar conexão.",
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleTest(id: number) {
    setTestingId(id);
    try {
      const r = await DataSourcesAPI.test(id);
      setTestResult((prev) => ({ ...prev, [id]: r }));
      await refresh();
    } finally {
      setTestingId(null);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Remover esta conexão?")) return;
    await DataSourcesAPI.delete(id);
    await refresh();
  }

  return (
    <PageContainer
      title="Data Sources"
      subtitle="Conexões cadastradas para uso em datasets e ETL. A demo não conecta a bancos externos reais."
      actions={
        canCreate && (
          <Button onClick={openModal}>+ Nova conexão</Button>
        )
      }
    >
      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <Card bodyClassName="p-0">
        {loading ? (
          <div className="p-8 text-center text-ink-500 text-sm">Carregando...</div>
        ) : items.length === 0 ? (
          <EmptyState
            title="Nenhuma conexão cadastrada"
            description={
              canCreate
                ? "Clique em + Nova conexão para começar."
                : "Você não tem permissão para criar conexões aqui."
            }
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-ink-50 text-left text-ink-700">
              <tr>
                <th className="px-4 py-2.5 font-semibold">Nome</th>
                <th className="px-4 py-2.5 font-semibold">Tipo</th>
                <th className="px-4 py-2.5 font-semibold">Host:Porta</th>
                <th className="px-4 py-2.5 font-semibold">Database</th>
                <th className="px-4 py-2.5 font-semibold">Workspace</th>
                <th className="px-4 py-2.5 font-semibold">Status</th>
                <th className="px-4 py-2.5 font-semibold text-right">Ações</th>
              </tr>
            </thead>
            <tbody>
              {items.map((ds) => (
                <tr key={ds.id} className="border-t border-ink-100">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-ink-900">{ds.connection_name}</div>
                    <div className="text-xs text-ink-500">
                      criada por {ds.created_by}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge tone="info">{ds.database_type}</Badge>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs">
                    {ds.host || "—"}:{ds.port || "—"}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs">
                    {ds.database_name || "—"}
                    {ds.schema && <span className="text-ink-400"> · {ds.schema}</span>}
                  </td>
                  <td className="px-4 py-2.5">{ds.workspace}</td>
                  <td className="px-4 py-2.5">
                    <Badge tone={STATUS_TONE[ds.status] ?? "neutral"}>{ds.status}</Badge>
                    {testResult[ds.id] && (
                      <div className="mt-1 text-[11px] text-ink-500">
                        {testResult[ds.id]?.latency_ms} ms
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        variant="ghost"
                        onClick={() => handleTest(ds.id)}
                        loading={testingId === ds.id}
                        className="text-xs"
                      >
                        Testar
                      </Button>
                      {canCreate && (
                        <Button
                          variant="ghost"
                          onClick={() => handleDelete(ds.id)}
                          className="text-xs text-rose-600 hover:bg-rose-50"
                        >
                          Remover
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Nova conexão de dados"
        subtitle="A senha não é persistida em texto puro. A conexão é simulada na demo."
        size="lg"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={creating}>
              Cancelar
            </Button>
            <Button onClick={submit} loading={creating} disabled={!draft.connection_name}>
              Criar conexão
            </Button>
          </div>
        }
      >
        {createError && (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {createError}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Nome da conexão *">
            <input
              value={draft.connection_name}
              onChange={(e) =>
                setDraft({ ...draft, connection_name: e.target.value })
              }
              className="input"
              placeholder="Ex.: Postgres_Finance_BR"
            />
          </Field>
          <Field label="Tipo">
            <select
              value={draft.database_type}
              onChange={(e) =>
                setDraft({ ...draft, database_type: e.target.value })
              }
              className="input"
            >
              {DB_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </Field>
          <Field label="Workspace">
            <select
              value={draft.workspace}
              onChange={(e) => setDraft({ ...draft, workspace: e.target.value })}
              className="input"
            >
              {workspaces.map((w) => (
                <option key={w}>{w}</option>
              ))}
            </select>
          </Field>
          <Field label="Host">
            <input
              value={draft.host ?? ""}
              onChange={(e) => setDraft({ ...draft, host: e.target.value })}
              className="input"
              placeholder="ex.: db.latam.internal"
            />
          </Field>
          <Field label="Porta">
            <input
              type="number"
              value={draft.port ?? 0}
              onChange={(e) =>
                setDraft({ ...draft, port: Number(e.target.value) || 0 })
              }
              className="input"
            />
          </Field>
          <Field label="Database">
            <input
              value={draft.database_name ?? ""}
              onChange={(e) =>
                setDraft({ ...draft, database_name: e.target.value })
              }
              className="input"
              placeholder="ex.: finance_br"
            />
          </Field>
          <Field label="Schema">
            <input
              value={draft.schema ?? ""}
              onChange={(e) => setDraft({ ...draft, schema: e.target.value })}
              className="input"
              placeholder="ex.: public"
            />
          </Field>
          <Field label="Username">
            <input
              value={draft.username ?? ""}
              onChange={(e) => setDraft({ ...draft, username: e.target.value })}
              className="input"
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              value={draft.password ?? ""}
              onChange={(e) => setDraft({ ...draft, password: e.target.value })}
              className="input"
              placeholder="armazenamos só o marcador 'tem senha'"
            />
          </Field>
          <Field label="Notas" full>
            <textarea
              value={draft.notes ?? ""}
              onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
              className="input min-h-[60px]"
              rows={2}
            />
          </Field>
        </div>
      </Modal>
    </PageContainer>
  );
}

function Field({
  label,
  children,
  full,
}: {
  label: string;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <label className={`block ${full ? "sm:col-span-2" : ""}`}>
      <span className="text-xs font-medium text-ink-700">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
