import { useMemo, useState } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";

interface DataTableProps<T extends Record<string, unknown>> {
  /** Lista de objetos. Cada chave vira uma coluna automaticamente. */
  data: T[];
  /** Se omitido, geramos colunas a partir das chaves do primeiro registro
   *  (ou de `columnsHint` quando fornecido). */
  columns?: ColumnDef<T, unknown>[];
  /** Quando data está vazio, este array decide as colunas (caso de preview vazio). */
  columnsHint?: string[];
  /** Tamanho de página inicial. */
  pageSize?: number;
  /** Habilita busca global (filtra qualquer coluna). */
  enableSearch?: boolean;
  /** Mensagem custom para estado vazio. */
  emptyMessage?: string;
  /** Altura máxima do corpo da tabela (deixa scrollar). */
  maxHeight?: string;
  /** Largura mínima de cada coluna (px). */
  minColumnWidth?: number;
}

function autoColumns<T extends Record<string, unknown>>(
  sample: T | undefined,
  hint: string[] | undefined,
): ColumnDef<T, unknown>[] {
  const ch = createColumnHelper<T>();
  const keys =
    sample && Object.keys(sample).length > 0
      ? Object.keys(sample)
      : hint ?? [];
  return keys.map((k) =>
    ch.accessor((row) => (row as Record<string, unknown>)[k], {
      id: k,
      header: () => <span className="capitalize">{k.replace(/_/g, " ")}</span>,
      cell: (info) => {
        const v = info.getValue();
        if (v === null || v === undefined || v === "") {
          return <span className="text-ink-300">—</span>;
        }
        if (typeof v === "number") {
          return (
            <span className="tabular-nums">
              {Number.isInteger(v)
                ? v.toLocaleString("en-US")
                : v.toLocaleString("en-US", { maximumFractionDigits: 4 })}
            </span>
          );
        }
        if (typeof v === "boolean") return <span>{v ? "true" : "false"}</span>;
        return <span>{String(v)}</span>;
      },
    }),
  );
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  columnsHint,
  pageSize = 25,
  enableSearch = true,
  emptyMessage = "Sem registros.",
  maxHeight = "480px",
  minColumnWidth = 120,
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  const cols = useMemo<ColumnDef<T, unknown>[]>(
    () => columns ?? autoColumns(data[0], columnsHint),
    [columns, columnsHint, data],
  );

  const table = useReactTable({
    data,
    columns: cols,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  });

  return (
    <div className="w-full">
      {enableSearch && (
        <div className="mb-3 flex items-center justify-between gap-3">
          <input
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder="Filtrar..."
            className="w-64 rounded-lg border border-ink-200 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200 focus:border-brand-400"
          />
          <div className="text-xs text-ink-500">
            {table.getFilteredRowModel().rows.length} linhas
          </div>
        </div>
      )}

      <div
        className="overflow-auto rounded-xl border border-ink-200 bg-white"
        style={{ maxHeight }}
      >
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-ink-50 z-10">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();
                  return (
                    <th
                      key={header.id}
                      className="px-3 py-2 text-left font-semibold text-ink-700 border-b border-ink-200 whitespace-nowrap"
                      style={{ minWidth: minColumnWidth }}
                    >
                      <button
                        type="button"
                        onClick={
                          canSort
                            ? header.column.getToggleSortingHandler()
                            : undefined
                        }
                        className={[
                          "inline-flex items-center gap-1",
                          canSort ? "hover:text-brand-700" : "cursor-default",
                        ].join(" ")}
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {sorted === "asc" && <span>▲</span>}
                        {sorted === "desc" && <span>▼</span>}
                      </button>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 && (
              <tr>
                <td
                  className="px-3 py-10 text-center text-ink-500"
                  colSpan={cols.length || 1}
                >
                  {emptyMessage}
                </td>
              </tr>
            )}
            {table.getRowModel().rows.map((row, idx) => (
              <tr
                key={row.id}
                className={idx % 2 === 0 ? "bg-white" : "bg-ink-50/50"}
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="px-3 py-2 border-b border-ink-100 whitespace-nowrap"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {table.getPageCount() > 1 && (
        <div className="mt-3 flex items-center justify-between text-sm">
          <div className="text-ink-500">
            Página {table.getState().pagination.pageIndex + 1} de{" "}
            {table.getPageCount()}
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => table.setPageIndex(0)}
              disabled={!table.getCanPreviousPage()}
              className="btn-ghost px-2 py-1 disabled:opacity-40"
            >
              «
            </button>
            <button
              type="button"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="btn-ghost px-2 py-1 disabled:opacity-40"
            >
              ‹
            </button>
            <button
              type="button"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="btn-ghost px-2 py-1 disabled:opacity-40"
            >
              ›
            </button>
            <button
              type="button"
              onClick={() => table.setPageIndex(table.getPageCount() - 1)}
              disabled={!table.getCanNextPage()}
              className="btn-ghost px-2 py-1 disabled:opacity-40"
            >
              »
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
