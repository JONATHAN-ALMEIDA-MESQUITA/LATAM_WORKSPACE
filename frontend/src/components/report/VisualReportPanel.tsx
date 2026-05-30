/**
 * Visual Report Builder — modo amigável sem SQL manual.
 */

import { useEffect, useMemo, useState } from "react";
import { DatasetsAPI, ReportsAPI } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type {
  DatasetColumn,
  DatasetSummary,
  JoinSuggestion,
  ReportPreviewResult,
  VisualFilter,
  VisualMetric,
} from "@/types";

const TABLE_ALIASES: Record<string, string> = {
  sales_latam: "sales",
  client_master: "clients",
  product_catalog: "products",
};

const FILTER_OPS: { value: VisualFilter["operator"]; label: string }[] = [
  { value: "eq", label: "igual a" },
  { value: "neq", label: "diferente de" },
  { value: "contains", label: "contém" },
  { value: "starts_with", label: "começa com" },
  { value: "gt", label: ">" },
  { value: "gte", label: ">=" },
  { value: "lt", label: "<" },
  { value: "lte", label: "<=" },
];

const AGG_OPTIONS = [
  { value: "sum", label: "Soma" },
  { value: "avg", label: "Média" },
  { value: "count", label: "Contagem" },
  { value: "min", label: "Mínimo" },
  { value: "max", label: "Máximo" },
] as const;

interface ColumnOption {
  table: string;
  column: string;
  dtype: string;
  label: string;
}

interface VisualReportPanelProps {
  datasets: DatasetSummary[];
  running: boolean;
  onRunningChange: (v: boolean) => void;
  onPreview: (result: ReportPreviewResult | null) => void;
  onError: (msg: string | null) => void;
  onSuccess: (msg: string | null) => void;
}

function tableAlias(name: string): string {
  return TABLE_ALIASES[name] ?? name.replace(/[^a-z0-9_]/gi, "_").slice(0, 20);
}

export function VisualReportPanel({
  datasets,
  running,
  onRunningChange,
  onPreview,
  onError,
  onSuccess,
}: VisualReportPanelProps) {
  const salesDatasets = useMemo(
    () =>
      datasets.filter((d) =>
        ["sales_latam", "client_master", "product_catalog"].includes(d.name),
      ),
    [datasets],
  );

  const [primaryId, setPrimaryId] = useState<number | "">("");
  const [joinEnabled, setJoinEnabled] = useState(false);
  const [joinId, setJoinId] = useState<number | "">("");
  const [joinType, setJoinType] = useState<"inner" | "left">("inner");
  const [joinSuggestion, setJoinSuggestion] = useState<JoinSuggestion | null>(null);

  const [primaryCols, setPrimaryCols] = useState<DatasetColumn[]>([]);
  const [joinCols, setJoinCols] = useState<DatasetColumn[]>([]);

  const [selectedCols, setSelectedCols] = useState<string[]>([]);
  const [summarize, setSummarize] = useState(false);
  const [groupBy, setGroupBy] = useState<string[]>([]);
  const [metricCol, setMetricCol] = useState("");
  const [metricAgg, setMetricAgg] = useState<VisualMetric["aggregation"]>("sum");
  const [filters, setFilters] = useState<VisualFilter[]>([]);
  const [orderCol, setOrderCol] = useState("");
  const [orderDir, setOrderDir] = useState<"asc" | "desc">("desc");

  const primary = datasets.find((d) => d.id === primaryId);
  const joinDs = datasets.find((d) => d.id === joinId);
  const primaryTable = primary ? tableAlias(primary.name) : "sales";
  const joinTable = joinDs ? tableAlias(joinDs.name) : "clients";

  const columnOptions: ColumnOption[] = useMemo(() => {
    const opts: ColumnOption[] = [];
    for (const c of primaryCols) {
      opts.push({
        table: primaryTable,
        column: c.name,
        dtype: c.dtype,
        label: `${primaryTable}.${c.name}`,
      });
    }
    if (joinEnabled && joinDs) {
      for (const c of joinCols) {
        opts.push({
          table: joinTable,
          column: c.name,
          dtype: c.dtype,
          label: `${joinTable}.${c.name}`,
        });
      }
    }
    return opts;
  }, [primaryCols, joinCols, joinEnabled, joinDs, primaryTable, joinTable]);

  const numericCols = columnOptions.filter((c) =>
    /int|float|double|decimal|numeric/i.test(c.dtype),
  );

  useEffect(() => {
    const sales = salesDatasets.find((d) => d.name === "sales_latam");
    if (sales) setPrimaryId(sales.id);
  }, [salesDatasets]);

  useEffect(() => {
    if (!primaryId) {
      setPrimaryCols([]);
      return;
    }
    DatasetsAPI.profile(Number(primaryId)).then(setPrimaryCols).catch(() => setPrimaryCols([]));
  }, [primaryId]);

  useEffect(() => {
    if (!joinEnabled || !joinId) {
      setJoinCols([]);
      return;
    }
    DatasetsAPI.profile(Number(joinId)).then(setJoinCols).catch(() => setJoinCols([]));
  }, [joinId, joinEnabled]);

  useEffect(() => {
    if (!primaryId || !joinEnabled || !joinId) {
      setJoinSuggestion(null);
      return;
    }
    ReportsAPI.joinSuggestions([Number(primaryId), Number(joinId)])
      .then((s) => setJoinSuggestion(s[0] ?? null))
      .catch(() => setJoinSuggestion(null));
  }, [primaryId, joinId, joinEnabled]);

  useEffect(() => {
    if (!joinEnabled) return;
    const client = salesDatasets.find((d) => d.name === "client_master");
    if (client && joinId !== client.id) setJoinId(client.id);
  }, [joinEnabled, salesDatasets, joinId]);

  function colKey(table: string, column: string) {
    return `${table}.${column}`;
  }

  function parseKey(key: string) {
    const [table, ...rest] = key.split(".");
    return { table, column: rest.join(".") };
  }

  function toggleCol(key: string) {
    setSelectedCols((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  }

  async function handleRun() {
    if (!primaryId) {
      onError("Selecione a tabela principal.");
      return;
    }
    onRunningChange(true);
    onError(null);
    onSuccess(null);
    try {
      const columns = summarize
        ? []
        : selectedCols.map((k) => {
            const { table, column } = parseKey(k);
            return { table, column };
          });

      const group_by = summarize
        ? groupBy.map((k) => {
            const { table, column } = parseKey(k);
            return { table, column };
          })
        : [];

      const metrics: VisualMetric[] = [];
      if (summarize && metricCol) {
        const { table, column } = parseKey(metricCol);
        metrics.push({ table, column, aggregation: metricAgg });
      }

      if (!summarize && columns.length === 0) {
        onError("Selecione ao menos uma coluna ou ative Resumir dados.");
        return;
      }
      if (summarize && group_by.length === 0) {
        onError("Selecione ao menos um campo em Agrupar por.");
        return;
      }

      let join = undefined;
      if (joinEnabled && joinId && joinSuggestion) {
        join = {
          dataset_id: Number(joinId),
          alias: joinTable,
          left_column: joinSuggestion.left,
          right_column: joinSuggestion.right,
          join_type: joinType,
        };
      }

      const order_by = orderCol ? parseKey(orderCol) : null;

      const result = await ReportsAPI.visualPreview({
        primary_dataset_id: Number(primaryId),
        join,
        columns,
        filters,
        group_by,
        metrics,
        order_by,
        order_dir: orderDir,
        limit: 200,
      });
      onPreview(result);
      onSuccess("Preview gerado.");
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (e instanceof Error ? e.message : "Erro ao gerar preview.");
      onError(typeof msg === "string" ? msg : JSON.stringify(msg));
      onPreview(null);
    } finally {
      onRunningChange(false);
    }
  }

  const joinOptions = salesDatasets.filter(
    (d) => d.id !== primaryId && d.name !== "sales_latam",
  );

  return (
    <div className="space-y-4">
      <Card title="1. Fontes de dados">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="block text-sm">
            Tabela principal (fato)
            <select
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={primaryId}
              onChange={(e) => {
                setPrimaryId(e.target.value ? Number(e.target.value) : "");
                setSelectedCols([]);
                setGroupBy([]);
              }}
            >
              <option value="">Selecione...</option>
              {salesDatasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} → alias <code>{tableAlias(d.name)}</code>
                </option>
              ))}
            </select>
          </label>

          <div className="text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={joinEnabled}
                onChange={(e) => setJoinEnabled(e.target.checked)}
              />
              Incluir join com outra tabela
            </label>
            {joinEnabled && (
              <div className="mt-2 space-y-2">
                <select
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={joinId}
                  onChange={(e) => setJoinId(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">Selecione...</option>
                  {joinOptions.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} → alias <code>{tableAlias(d.name)}</code>
                    </option>
                  ))}
                </select>
                <select
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={joinType}
                  onChange={(e) => setJoinType(e.target.value as "inner" | "left")}
                >
                  <option value="inner">INNER JOIN</option>
                  <option value="left">LEFT JOIN</option>
                </select>
                {joinSuggestion && (
                  <p className="text-xs text-slate-500">
                    Join sugerido: <code>{joinSuggestion.left}</code> ={" "}
                    <code>{joinSuggestion.right}</code>
                    {joinSuggestion.label ? ` (${joinSuggestion.label})` : ""}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </Card>

      <Card title="2. Colunas">
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={summarize}
            onChange={(e) => {
              setSummarize(e.target.checked);
              if (e.target.checked) setSelectedCols([]);
            }}
          />
          Resumir dados (agrupar + métrica)
        </label>

        {!summarize ? (
          <div className="grid max-h-56 gap-1 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
            {columnOptions.map((c) => {
              const key = colKey(c.table, c.column);
              return (
                <label key={key} className="flex items-center gap-2 rounded px-2 py-1 text-xs hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={selectedCols.includes(key)}
                    onChange={() => toggleCol(key)}
                  />
                  <span className="font-mono">{c.label}</span>
                  <span className="text-slate-400">({c.dtype})</span>
                </label>
              );
            })}
          </div>
        ) : (
          <div className="space-y-3">
            <div>
              <p className="mb-1 text-xs font-medium text-slate-600">Agrupar por</p>
              <div className="grid max-h-40 gap-1 overflow-y-auto sm:grid-cols-2">
                {columnOptions.map((c) => {
                  const key = colKey(c.table, c.column);
                  return (
                    <label key={key} className="flex items-center gap-2 text-xs">
                      <input
                        type="checkbox"
                        checked={groupBy.includes(key)}
                        onChange={() =>
                          setGroupBy((prev) =>
                            prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
                          )
                        }
                      />
                      <span className="font-mono">{c.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                Métrica (coluna numérica)
                <select
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={metricCol}
                  onChange={(e) => setMetricCol(e.target.value)}
                >
                  <option value="">Selecione...</option>
                  {numericCols.map((c) => (
                    <option key={colKey(c.table, c.column)} value={colKey(c.table, c.column)}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                Agregação
                <select
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  value={metricAgg}
                  onChange={(e) =>
                    setMetricAgg(e.target.value as VisualMetric["aggregation"])
                  }
                >
                  {AGG_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        )}
      </Card>

      <Card title="3. Filtros (opcional)">
        {filters.length === 0 && (
          <p className="mb-2 text-xs text-slate-500">Nenhum filtro. Adicione para refinar o report.</p>
        )}
        <div className="space-y-2">
          {filters.map((f, idx) => (
            <div key={idx} className="flex flex-wrap items-end gap-2">
              <select
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
                value={colKey(f.table, f.column)}
                onChange={(e) => {
                  const { table, column } = parseKey(e.target.value);
                  setFilters((prev) => {
                    const next = [...prev];
                    next[idx] = { ...next[idx], table, column };
                    return next;
                  });
                }}
              >
                {columnOptions.map((c) => (
                  <option key={colKey(c.table, c.column)} value={colKey(c.table, c.column)}>
                    {c.label}
                  </option>
                ))}
              </select>
              <select
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
                value={f.operator}
                onChange={(e) => {
                  setFilters((prev) => {
                    const next = [...prev];
                    next[idx] = {
                      ...next[idx],
                      operator: e.target.value as VisualFilter["operator"],
                    };
                    return next;
                  });
                }}
              >
                {FILTER_OPS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <input
                className="rounded border border-slate-300 px-2 py-1.5 text-xs"
                value={f.value}
                placeholder="valor"
                onChange={(e) => {
                  setFilters((prev) => {
                    const next = [...prev];
                    next[idx] = { ...next[idx], value: e.target.value };
                    return next;
                  });
                }}
              />
              <Button
                variant="secondary"
                onClick={() => setFilters((prev) => prev.filter((_, i) => i !== idx))}
              >
                Remover
              </Button>
            </div>
          ))}
        </div>
        <Button
          variant="secondary"
          className="mt-2"
          disabled={columnOptions.length === 0}
          onClick={() => {
            const first = columnOptions[0];
            if (!first) return;
            setFilters((prev) => [
              ...prev,
              {
                table: first.table,
                column: first.column,
                operator: "eq",
                value: "",
              },
            ]);
          }}
        >
          + Adicionar filtro
        </Button>
      </Card>

      <Card title="4. Ordenação">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            Ordenar por
            <select
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={orderCol}
              onChange={(e) => setOrderCol(e.target.value)}
            >
              <option value="">Padrão</option>
              {columnOptions.map((c) => (
                <option key={colKey(c.table, c.column)} value={colKey(c.table, c.column)}>
                  {c.label}
                </option>
              ))}
              {summarize && metricCol && (
                <option value={metricCol}>{metricCol} (métrica)</option>
              )}
            </select>
          </label>
          <label className="block text-sm">
            Direção
            <select
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={orderDir}
              onChange={(e) => setOrderDir(e.target.value as "asc" | "desc")}
            >
              <option value="desc">Decrescente</option>
              <option value="asc">Crescente</option>
            </select>
          </label>
        </div>
      </Card>

      <div className="flex justify-end">
        <Button variant="primary" onClick={handleRun} disabled={running || !primaryId}>
          {running ? "Gerando..." : "Executar preview"}
        </Button>
      </div>
    </div>
  );
}
