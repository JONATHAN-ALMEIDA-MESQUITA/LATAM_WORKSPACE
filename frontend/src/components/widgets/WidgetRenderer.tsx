/**
 * WidgetRenderer - renderiza qualquer tipo de widget a partir do payload
 * vindo do backend (`/dashboards/{id}/render` ou `/dashboards/widgets/preview`).
 *
 * Tipos suportados:
 *   - kpi_card      (valor + label)
 *   - bar_chart     (barras verticais)
 *   - line_chart    (linha temporal)
 *   - area_chart    (área preenchida)
 *   - pie_chart     (pizza)
 *   - donut_chart   (pizza com furo)
 *   - table         (tabela com paginação simples)
 *   - text_box      (markdown-like / texto longo)
 */

import { useMemo } from "react";
// Import via factory para contornar bug do dep optimizer do Vite v5
// com pacotes CJS que têm ".js" no nome (react-plotly.js).
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

import type { WidgetRenderResult } from "@/types";

const Plot = createPlotlyComponent(Plotly);

interface Props {
  result: WidgetRenderResult;
  className?: string;
  height?: number | string;
}

const COLOR_PALETTE = [
  "#2563eb", "#0ea5e9", "#10b981", "#f59e0b",
  "#ef4444", "#a855f7", "#ec4899", "#14b8a6",
  "#6366f1", "#84cc16",
];

function formatValue(
  value: number | null | undefined,
  output_format: string,
  decimals: number,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (output_format === "percent") return `${(value * 100).toFixed(decimals)}%`;
  if (output_format === "currency") {
    return `$ ${value.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`;
  }
  if (output_format === "integer") {
    return Math.round(value).toLocaleString("en-US");
  }
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function WidgetRenderer({ result, className = "", height = "100%" }: Props) {
  if (result.notes) {
    return (
      <div className={`flex h-full flex-col items-center justify-center rounded-md border border-amber-300 bg-amber-50 p-3 text-center text-sm text-amber-800 ${className}`}>
        <div className="font-semibold">{result.title || "Widget"}</div>
        <div className="text-xs mt-1">{result.notes}</div>
      </div>
    );
  }

  // KPI
  if (result.widget_type === "kpi_card" && result.kpi) {
    const k = result.kpi;
    const positive = (k.value ?? 0) >= 0;
    return (
      <div className={`flex h-full flex-col justify-center rounded-md border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
        <div className="text-xs uppercase tracking-wide text-slate-500">
          {k.label || result.title}
        </div>
        <div
          className={`mt-1 text-3xl font-bold ${
            k.output_format === "percent"
              ? positive
                ? "text-emerald-600"
                : "text-rose-600"
              : "text-slate-900"
          }`}
        >
          {k.formatted}
        </div>
        <div className="mt-2 text-[11px] text-slate-400">
          {result.rows_used.toLocaleString("en-US")} linhas usadas
        </div>
      </div>
    );
  }

  // Text Box
  if (result.widget_type === "text_box") {
    return (
      <div className={`flex h-full flex-col rounded-md border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
        {result.title && (
          <div className="mb-2 text-sm font-semibold text-slate-700">{result.title}</div>
        )}
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
          {(result.text || "").split("**").map((chunk, idx) =>
            idx % 2 === 1 ? <strong key={idx}>{chunk}</strong> : <span key={idx}>{chunk}</span>,
          )}
        </div>
      </div>
    );
  }

  // Table
  if (result.widget_type === "table" && result.table) {
    const { columns, rows, total_rows } = result.table;
    return (
      <div className={`flex h-full flex-col rounded-md border border-slate-200 bg-white shadow-sm ${className}`}>
        <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
          <div className="text-sm font-semibold text-slate-700">{result.title}</div>
          <div className="text-xs text-slate-400">
            {rows.length} / {total_rows.toLocaleString("en-US")} linhas
          </div>
        </div>
        <div className="flex-1 overflow-auto">
          <table className="min-w-full text-xs">
            <thead className="sticky top-0 bg-slate-50">
              <tr>
                {columns.map((c) => (
                  <th key={c} className="border-b border-slate-200 px-3 py-2 text-left font-semibold text-slate-600">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                  {columns.map((c) => {
                    const v = row[c];
                    let display: string;
                    if (v === null || v === undefined) display = "—";
                    else if (typeof v === "number")
                      display = v.toLocaleString("en-US", { maximumFractionDigits: 2 });
                    else display = String(v);
                    return (
                      <td key={c} className="px-3 py-1.5 text-slate-700">
                        {display}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // Charts
  if (result.chart) {
    const { categories, series, output_format, decimals } = result.chart;
    const colors = COLOR_PALETTE;

    let plotData: any[] = [];
    let layout: any = {
      autosize: true,
      margin: { l: 50, r: 20, t: 10, b: 50 },
      font: { family: "Inter, system-ui, sans-serif", size: 11, color: "#475569" },
      paper_bgcolor: "white",
      plot_bgcolor: "white",
      xaxis: { gridcolor: "#e2e8f0", zeroline: false },
      yaxis: {
        gridcolor: "#e2e8f0",
        zeroline: false,
        tickformat: output_format === "percent" ? ".1%" : undefined,
      },
      hovermode: "closest",
    };

    const seriesValues = series[0]?.values ?? [];

    if (result.widget_type === "bar_chart") {
      plotData = [
        {
          type: "bar",
          x: categories.map((c) => String(c)),
          y: seriesValues,
          marker: { color: colors[0] },
          hovertemplate: "<b>%{x}</b><br>%{y}<extra></extra>",
        },
      ];
    } else if (result.widget_type === "line_chart") {
      plotData = [
        {
          type: "scatter",
          mode: "lines+markers",
          x: categories.map((c) => String(c)),
          y: seriesValues,
          line: { color: colors[0], width: 2 },
          marker: { color: colors[0], size: 6 },
          hovertemplate: "<b>%{x}</b><br>%{y}<extra></extra>",
        },
      ];
    } else if (result.widget_type === "area_chart") {
      plotData = [
        {
          type: "scatter",
          mode: "lines",
          x: categories.map((c) => String(c)),
          y: seriesValues,
          fill: "tozeroy",
          line: { color: colors[0], width: 2 },
          fillcolor: "rgba(37, 99, 235, 0.18)",
          hovertemplate: "<b>%{x}</b><br>%{y}<extra></extra>",
        },
      ];
    } else if (result.widget_type === "pie_chart" || result.widget_type === "donut_chart") {
      plotData = [
        {
          type: "pie",
          labels: categories.map((c) => String(c)),
          values: seriesValues.map((v) => v ?? 0),
          marker: { colors: colors },
          hole: result.widget_type === "donut_chart" ? 0.45 : 0,
          textinfo: "label+percent",
          textposition: "outside",
          hovertemplate: "<b>%{label}</b><br>%{value}<extra></extra>",
        },
      ];
      layout = {
        ...layout,
        margin: { l: 10, r: 10, t: 10, b: 10 },
        showlegend: false,
      };
    }

    return (
      <div className={`flex h-full flex-col rounded-md border border-slate-200 bg-white shadow-sm ${className}`}>
        <div className="border-b border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">
          {result.title}
        </div>
        <div className="flex-1">
          <Plot
            data={plotData}
            layout={layout}
            style={{ width: "100%", height: typeof height === "number" ? `${height}px` : height }}
            useResizeHandler
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>
      </div>
    );
  }

  // Fallback
  return (
    <div className={`flex h-full flex-col items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-sm text-slate-500 ${className}`}>
      <div className="font-semibold">{result.title || "Widget"}</div>
      <div className="text-xs mt-1">Sem dados disponíveis ({result.widget_type})</div>
    </div>
  );
}
