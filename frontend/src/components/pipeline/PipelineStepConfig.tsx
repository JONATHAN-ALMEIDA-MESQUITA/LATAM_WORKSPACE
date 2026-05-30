/**
 * Config dinamico por tipo de step do Pipeline Studio.
 *
 * Recebe step_type + config + colunas disponiveis (do output do step anterior)
 * e renderiza o formulario adequado. As mudancas sao propagadas via onChange.
 */

import type { DatasetSummary, StepType } from "@/types";

interface Props {
  stepType: StepType | string;
  config: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
  datasets: DatasetSummary[];
  upstreamColumns: { name: string; dtype: string }[];
}

const FILTER_OPS = [
  { value: "==", label: "= (igual)" },
  { value: "!=", label: "!= (diferente)" },
  { value: ">", label: "> (maior)" },
  { value: "<", label: "< (menor)" },
  { value: ">=", label: ">=" },
  { value: "<=", label: "<=" },
  { value: "in", label: "in (lista)" },
  { value: "not_in", label: "not in" },
  { value: "contains", label: "contains (texto)" },
  { value: "is_null", label: "is null" },
  { value: "is_not_null", label: "is not null" },
];

const AGG_FUNCS = [
  { value: "sum", label: "sum" },
  { value: "avg", label: "avg" },
  { value: "min", label: "min" },
  { value: "max", label: "max" },
  { value: "count", label: "count" },
  { value: "nunique", label: "nunique (distintos)" },
];

const JOIN_HOWS = [
  { value: "left", label: "LEFT JOIN" },
  { value: "inner", label: "INNER JOIN" },
  { value: "right", label: "RIGHT JOIN" },
  { value: "outer", label: "FULL OUTER JOIN" },
];

const BUSINESS_AREAS = ["", "Sales", "Finance", "Operations", "Supplier", "HR", "Executive"];

type FilterCondition = { col?: string; op?: string; value?: unknown };
type AggSpec = { col?: string; func?: string; as?: string };

export function PipelineStepConfig({ stepType, config, onChange, datasets, upstreamColumns }: Props) {
  function set<K extends string>(key: K, value: unknown) {
    onChange({ ...config, [key]: value });
  }

  function colOptions() {
    return upstreamColumns.map((c) => ({ value: c.name, label: `${c.name} (${c.dtype})` }));
  }

  // ----- SOURCE -----
  if (stepType === "source") {
    return (
      <div>
        <label className="text-xs font-semibold text-slate-600">Dataset *</label>
        <select
          className="input"
          value={(config.dataset_id as number | undefined) ?? ""}
          onChange={(e) => set("dataset_id", e.target.value ? Number(e.target.value) : undefined)}
        >
          <option value="">Selecione...</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name} ({d.workspace}, {d.row_count} rows)
            </option>
          ))}
        </select>
        <div className="mt-2 text-[11px] text-slate-500">
          Carrega o dataset escolhido como entrada do pipeline.
        </div>
      </div>
    );
  }

  // ----- FILTER -----
  if (stepType === "filter") {
    const conditions = (config.conditions as FilterCondition[]) ?? [];
    function addCond() {
      onChange({ ...config, conditions: [...conditions, { col: "", op: "==", value: "" }] });
    }
    function rmCond(i: number) {
      onChange({ ...config, conditions: conditions.filter((_, idx) => idx !== i) });
    }
    function updCond(i: number, patch: Partial<FilterCondition>) {
      onChange({
        ...config,
        conditions: conditions.map((c, idx) => (idx === i ? { ...c, ...patch } : c)),
      });
    }
    return (
      <div className="space-y-2">
        <div className="text-xs text-slate-600">Condicoes (AND)</div>
        {conditions.length === 0 && (
          <div className="text-[11px] text-slate-500">Nenhuma condicao. Tudo passa.</div>
        )}
        {conditions.map((c, i) => (
          <div key={i} className="grid grid-cols-12 gap-1">
            <select
              className="input col-span-4 text-xs"
              value={c.col ?? ""}
              onChange={(e) => updCond(i, { col: e.target.value })}
            >
              <option value="">coluna...</option>
              {colOptions().map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              className="input col-span-3 text-xs"
              value={c.op ?? "=="}
              onChange={(e) => updCond(i, { op: e.target.value })}
            >
              {FILTER_OPS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <input
              className="input col-span-4 text-xs"
              placeholder={
                c.op === "in" || c.op === "not_in" ? "v1, v2, v3" : "valor"
              }
              value={Array.isArray(c.value) ? (c.value as string[]).join(", ") : String(c.value ?? "")}
              onChange={(e) => {
                const raw = e.target.value;
                if (c.op === "in" || c.op === "not_in") {
                  updCond(i, { value: raw.split(",").map((s) => s.trim()).filter(Boolean) });
                } else {
                  updCond(i, { value: raw });
                }
              }}
              disabled={c.op === "is_null" || c.op === "is_not_null"}
            />
            <button
              type="button"
              className="col-span-1 text-rose-600 hover:underline text-xs"
              onClick={() => rmCond(i)}
            >
              x
            </button>
          </div>
        ))}
        <button
          type="button"
          className="text-xs text-brand-600 hover:underline"
          onClick={addCond}
        >
          + adicionar condicao
        </button>
      </div>
    );
  }

  // ----- SELECT -----
  if (stepType === "select") {
    const columns = (config.columns as string[]) ?? [];
    const rename = (config.rename as Record<string, string>) ?? {};
    function toggleCol(name: string) {
      const next = columns.includes(name)
        ? columns.filter((c) => c !== name)
        : [...columns, name];
      onChange({ ...config, columns: next });
    }
    return (
      <div className="space-y-2">
        <div className="text-xs text-slate-600">
          Colunas selecionadas: {columns.length || "todas"}
        </div>
        <div className="max-h-44 overflow-auto rounded border bg-white p-2">
          {upstreamColumns.length === 0 ? (
            <div className="text-[11px] text-slate-500">
              Rode o preview do step anterior para ver as colunas disponiveis.
            </div>
          ) : (
            upstreamColumns.map((c) => (
              <label key={c.name} className="flex items-center gap-2 py-0.5 text-xs">
                <input
                  type="checkbox"
                  checked={columns.length === 0 ? false : columns.includes(c.name)}
                  onChange={() => toggleCol(c.name)}
                />
                <span>{c.name}</span>
                <span className="text-[10px] text-slate-400">({c.dtype})</span>
              </label>
            ))
          )}
        </div>
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-600">Renomear colunas (opcional)</summary>
          <div className="mt-1 space-y-1">
            {columns.map((col) => (
              <div key={col} className="flex items-center gap-1">
                <span className="w-32 truncate text-[11px]">{col}</span>
                <span>=&gt;</span>
                <input
                  className="input text-xs"
                  placeholder={col}
                  value={rename[col] ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    const next = { ...rename };
                    if (v) next[col] = v;
                    else delete next[col];
                    onChange({ ...config, rename: next });
                  }}
                />
              </div>
            ))}
          </div>
        </details>
      </div>
    );
  }

  // ----- COMPUTED -----
  if (stepType === "computed") {
    return (
      <div className="space-y-2">
        <div>
          <label className="text-xs font-semibold text-slate-600">Nova coluna *</label>
          <input
            className="input"
            value={(config.new_col as string) ?? ""}
            onChange={(e) => set("new_col", e.target.value)}
            placeholder="Ex: margin_pct"
          />
        </div>
        <div>
          <label className="text-xs font-semibold text-slate-600">Expressao *</label>
          <input
            className="input font-mono text-xs"
            value={(config.expression as string) ?? ""}
            onChange={(e) => set("expression", e.target.value)}
            placeholder="Ex: (revenue - cost) / revenue"
          />
          <div className="mt-1 text-[11px] text-slate-500">
            Suporta operadores aritmeticos (+ - * /), comparacoes (==, &gt;, &lt;), & |.
            Use nomes de colunas como variaveis. Avaliado por pandas.eval (seguro).
          </div>
        </div>
      </div>
    );
  }

  // ----- GROUP_BY -----
  if (stepType === "group_by") {
    const by = (config.by as string[]) ?? [];
    const aggs = (config.aggs as AggSpec[]) ?? [];
    function addAgg() {
      onChange({ ...config, aggs: [...aggs, { col: "", func: "sum", as: "" }] });
    }
    function rmAgg(i: number) {
      onChange({ ...config, aggs: aggs.filter((_, idx) => idx !== i) });
    }
    function updAgg(i: number, patch: Partial<AggSpec>) {
      onChange({
        ...config,
        aggs: aggs.map((a, idx) => (idx === i ? { ...a, ...patch } : a)),
      });
    }
    function toggleBy(col: string) {
      const next = by.includes(col) ? by.filter((c) => c !== col) : [...by, col];
      onChange({ ...config, by: next });
    }
    return (
      <div className="space-y-3">
        <div>
          <div className="text-xs font-semibold text-slate-600">Agrupar por *</div>
          <div className="mt-1 max-h-32 overflow-auto rounded border bg-white p-2">
            {upstreamColumns.length === 0 ? (
              <div className="text-[11px] text-slate-500">Sem colunas (rode preview).</div>
            ) : (
              upstreamColumns.map((c) => (
                <label key={c.name} className="flex items-center gap-2 py-0.5 text-xs">
                  <input
                    type="checkbox"
                    checked={by.includes(c.name)}
                    onChange={() => toggleBy(c.name)}
                  />
                  <span>{c.name}</span>
                  <span className="text-[10px] text-slate-400">({c.dtype})</span>
                </label>
              ))
            )}
          </div>
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-600">Agregacoes *</div>
          {aggs.map((a, i) => (
            <div key={i} className="mt-1 grid grid-cols-12 gap-1">
              <select
                className="input col-span-3 text-xs"
                value={a.func ?? "sum"}
                onChange={(e) => updAgg(i, { func: e.target.value })}
              >
                {AGG_FUNCS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <select
                className="input col-span-4 text-xs"
                value={a.col ?? ""}
                onChange={(e) => updAgg(i, { col: e.target.value })}
              >
                <option value="">coluna...</option>
                {colOptions().map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <input
                className="input col-span-4 text-xs"
                placeholder="alias (ex: revenue_total)"
                value={a.as ?? ""}
                onChange={(e) => updAgg(i, { as: e.target.value })}
              />
              <button
                type="button"
                className="col-span-1 text-rose-600 hover:underline text-xs"
                onClick={() => rmAgg(i)}
              >
                x
              </button>
            </div>
          ))}
          <button
            type="button"
            className="mt-1 text-xs text-brand-600 hover:underline"
            onClick={addAgg}
          >
            + adicionar agregacao
          </button>
        </div>
      </div>
    );
  }

  // ----- JOIN -----
  if (stepType === "join") {
    return (
      <div className="space-y-2">
        <div>
          <label className="text-xs font-semibold text-slate-600">Dataset da direita *</label>
          <select
            className="input"
            value={(config.right_dataset_id as number | undefined) ?? ""}
            onChange={(e) =>
              set("right_dataset_id", e.target.value ? Number(e.target.value) : undefined)
            }
          >
            <option value="">Selecione...</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.workspace})
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <div>
            <label className="text-xs font-semibold text-slate-600">Tipo *</label>
            <select
              className="input"
              value={(config.how as string) ?? "left"}
              onChange={(e) => set("how", e.target.value)}
            >
              {JOIN_HOWS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">left_on *</label>
            <select
              className="input"
              value={(config.left_on as string) ?? ""}
              onChange={(e) => set("left_on", e.target.value)}
            >
              <option value="">coluna...</option>
              {colOptions().map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">right_on *</label>
            <input
              className="input"
              value={(config.right_on as string) ?? ""}
              onChange={(e) => set("right_on", e.target.value)}
              placeholder="nome da coluna no dataset direito"
            />
          </div>
        </div>
        <div>
          <label className="text-xs font-semibold text-slate-600">
            Suffix para colunas duplicadas
          </label>
          <input
            className="input"
            value={(config.suffix as string) ?? "_right"}
            onChange={(e) => set("suffix", e.target.value)}
            placeholder="_right"
          />
        </div>
      </div>
    );
  }

  // ----- UNION -----
  if (stepType === "union") {
    const dsIds = (config.datasets as number[]) ?? [];
    function toggle(id: number) {
      const next = dsIds.includes(id) ? dsIds.filter((x) => x !== id) : [...dsIds, id];
      onChange({ ...config, datasets: next });
    }
    return (
      <div>
        <div className="text-xs text-slate-600">
          Selecione datasets para concatenar (UNION ALL).
        </div>
        <div className="mt-1 max-h-44 overflow-auto rounded border bg-white p-2">
          {datasets.map((d) => (
            <label key={d.id} className="flex items-center gap-2 py-0.5 text-xs">
              <input
                type="checkbox"
                checked={dsIds.includes(d.id)}
                onChange={() => toggle(d.id)}
              />
              <span>
                {d.name} <span className="text-slate-400">({d.row_count} rows)</span>
              </span>
            </label>
          ))}
        </div>
      </div>
    );
  }

  // ----- SORT -----
  if (stepType === "sort") {
    const by = (config.by as string[]) ?? [];
    const asc = (config.ascending as boolean[]) ?? [];
    function setByAt(i: number, col: string) {
      const nb = [...by];
      nb[i] = col;
      onChange({ ...config, by: nb });
    }
    function setAscAt(i: number, val: boolean) {
      const na = [...asc];
      na[i] = val;
      onChange({ ...config, ascending: na });
    }
    function addCol() {
      onChange({ ...config, by: [...by, ""], ascending: [...asc, true] });
    }
    function rmCol(i: number) {
      onChange({
        ...config,
        by: by.filter((_, idx) => idx !== i),
        ascending: asc.filter((_, idx) => idx !== i),
      });
    }
    return (
      <div className="space-y-2">
        <div className="text-xs text-slate-600">Ordenar por (na ordem):</div>
        {by.map((col, i) => (
          <div key={i} className="grid grid-cols-12 gap-1">
            <select
              className="input col-span-7 text-xs"
              value={col}
              onChange={(e) => setByAt(i, e.target.value)}
            >
              <option value="">coluna...</option>
              {colOptions().map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              className="input col-span-4 text-xs"
              value={asc[i] === false ? "desc" : "asc"}
              onChange={(e) => setAscAt(i, e.target.value === "asc")}
            >
              <option value="asc">Crescente</option>
              <option value="desc">Decrescente</option>
            </select>
            <button
              type="button"
              className="col-span-1 text-rose-600 hover:underline text-xs"
              onClick={() => rmCol(i)}
            >
              x
            </button>
          </div>
        ))}
        <button
          type="button"
          className="text-xs text-brand-600 hover:underline"
          onClick={addCol}
        >
          + adicionar coluna
        </button>
      </div>
    );
  }

  // ----- LIMIT -----
  if (stepType === "limit") {
    return (
      <div>
        <label className="text-xs font-semibold text-slate-600">Top N rows *</label>
        <input
          type="number"
          className="input"
          min={1}
          value={(config.n as number) ?? 1000}
          onChange={(e) => set("n", Number(e.target.value))}
        />
      </div>
    );
  }

  // ----- TARGET -----
  if (stepType === "target") {
    return (
      <div className="space-y-2">
        <div>
          <label className="text-xs font-semibold text-slate-600">Nome do dataset gerado *</label>
          <input
            className="input"
            value={(config.dataset_name as string) ?? ""}
            onChange={(e) => set("dataset_name", e.target.value)}
            placeholder="Ex: Brazil Top Clients"
          />
        </div>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <div>
            <label className="text-xs font-semibold text-slate-600">Workspace</label>
            <input
              className="input"
              value={(config.workspace as string) ?? "LATAM"}
              onChange={(e) => set("workspace", e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-600">Business area</label>
            <select
              className="input"
              value={(config.business_area as string) ?? ""}
              onChange={(e) => set("business_area", e.target.value)}
            >
              {BUSINESS_AREAS.map((a) => (
                <option key={a} value={a}>
                  {a || "(nenhuma)"}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="text-xs font-semibold text-slate-600">Descricao</label>
          <textarea
            className="input min-h-[50px]"
            value={(config.description as string) ?? ""}
            onChange={(e) => set("description", e.target.value)}
          />
        </div>
        <div className="text-[11px] text-slate-500">
          O DataFrame final sera gravado como Parquet + registrado como Dataset (source=ETL Output).
          Ficara disponivel automaticamente no Metric Builder e Dashboard Builder.
        </div>
      </div>
    );
  }

  return <div className="text-xs text-slate-500">Tipo de step nao suportado.</div>;
}
