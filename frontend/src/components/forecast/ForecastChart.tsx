/**
 * ForecastChart - grafico Plotly para visualizar resultado de forecast.
 *
 * Renderiza:
 *   - Serie historica (y)             linha solida
 *   - Backtest (yhat no holdout)      linha tracejada azul
 *   - Forecast futuro (yhat)          linha amarela
 *   - Banda de confianca              area cinza translucida
 *
 * Suporta multiplas series (group_by): cada grupo vira um trace separado,
 * com toggle interativo via legenda do Plotly.
 */

import { useMemo } from "react";
import Plotly from "plotly.js-dist-min";
import createPlotlyComponent from "react-plotly.js/factory";

import type { ForecastPoint } from "@/types";

const Plot = createPlotlyComponent(Plotly);

interface Props {
  points: ForecastPoint[];
  height?: number;
  showConfidenceBand?: boolean;
}

interface GroupBundle {
  key: string;
  history: { ds: string[]; y: number[] };
  backtest: { ds: string[]; yhat: number[] };
  forecast: { ds: string[]; yhat: number[]; lower: number[]; upper: number[] };
}

function groupByKey(points: ForecastPoint[]): GroupBundle[] {
  const groups = new Map<string, GroupBundle>();
  for (const p of points) {
    const key = p.group_key ?? "__global__";
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        history: { ds: [], y: [] },
        backtest: { ds: [], yhat: [] },
        forecast: { ds: [], yhat: [], lower: [], upper: [] },
      });
    }
    const bundle = groups.get(key)!;
    if (p.is_forecast) {
      bundle.forecast.ds.push(p.ds);
      bundle.forecast.yhat.push(p.yhat ?? 0);
      bundle.forecast.lower.push(p.yhat_lower ?? 0);
      bundle.forecast.upper.push(p.yhat_upper ?? 0);
    } else {
      if (p.y !== null) {
        bundle.history.ds.push(p.ds);
        bundle.history.y.push(p.y);
      }
      if (p.yhat !== null) {
        bundle.backtest.ds.push(p.ds);
        bundle.backtest.yhat.push(p.yhat);
      }
    }
  }
  return Array.from(groups.values()).sort((a, b) => a.key.localeCompare(b.key));
}

// Paleta para grupos
const COLORS = [
  "#2563eb",
  "#dc2626",
  "#16a34a",
  "#ea580c",
  "#9333ea",
  "#0891b2",
  "#ca8a04",
  "#db2777",
  "#475569",
];

export function ForecastChart({ points, height = 450, showConfidenceBand = true }: Props) {
  const traces = useMemo(() => {
    const bundles = groupByKey(points);
    const out: Plotly.Data[] = [];

    bundles.forEach((bundle, i) => {
      const color = COLORS[i % COLORS.length];
      const isMulti = bundles.length > 1;
      const groupLabel = isMulti ? bundle.key : "Serie";

      if (bundle.history.ds.length > 0) {
        out.push({
          x: bundle.history.ds,
          y: bundle.history.y,
          type: "scatter",
          mode: "lines+markers",
          name: `${groupLabel} - Historico`,
          line: { color, width: 2 },
          marker: { size: 4 },
          legendgroup: bundle.key,
        });
      }

      if (bundle.backtest.ds.length > 0) {
        out.push({
          x: bundle.backtest.ds,
          y: bundle.backtest.yhat,
          type: "scatter",
          mode: "lines",
          name: `${groupLabel} - Backtest`,
          line: { color, width: 1.5, dash: "dash" },
          legendgroup: bundle.key,
        });
      }

      if (bundle.forecast.ds.length > 0) {
        // Banda de confianca (apenas se 1 grupo, ou se showConfidenceBand)
        if (showConfidenceBand && (!isMulti || bundles.length <= 3)) {
          out.push({
            x: [...bundle.forecast.ds, ...bundle.forecast.ds.slice().reverse()],
            y: [...bundle.forecast.upper, ...bundle.forecast.lower.slice().reverse()],
            type: "scatter",
            fill: "toself",
            fillcolor: hexToRgba(color, 0.15),
            line: { color: "transparent" },
            name: `${groupLabel} - IC 95%`,
            legendgroup: bundle.key,
            showlegend: !isMulti,
            hoverinfo: "skip",
          });
        }

        out.push({
          x: bundle.forecast.ds,
          y: bundle.forecast.yhat,
          type: "scatter",
          mode: "lines+markers",
          name: `${groupLabel} - Forecast`,
          line: { color, width: 2.5 },
          marker: { size: 6, symbol: "diamond" },
          legendgroup: bundle.key,
        });
      }
    });

    return out;
  }, [points, showConfidenceBand]);

  const layout = useMemo<Partial<Plotly.Layout>>(
    () => ({
      autosize: true,
      height,
      margin: { l: 60, r: 20, t: 30, b: 50 },
      xaxis: { title: { text: "Data" }, gridcolor: "#e2e8f0" },
      yaxis: { title: { text: "Valor" }, gridcolor: "#e2e8f0", separatethousands: true },
      legend: { orientation: "h", y: -0.2, font: { size: 11 } },
      hovermode: "x unified",
      plot_bgcolor: "#ffffff",
      paper_bgcolor: "#ffffff",
      shapes: getForecastShape(points),
    }),
    [points, height],
  );

  return (
    <Plot
      data={traces}
      layout={layout}
      style={{ width: "100%" }}
      config={{ displayModeBar: true, displaylogo: false, responsive: true }}
      useResizeHandler
    />
  );
}

function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function getForecastShape(points: ForecastPoint[]): Partial<Plotly.Shape>[] {
  const firstFuture = points.find((p) => p.is_forecast);
  if (!firstFuture) return [];
  return [
    {
      type: "line",
      x0: firstFuture.ds,
      x1: firstFuture.ds,
      yref: "paper",
      y0: 0,
      y1: 1,
      line: { color: "#94a3b8", width: 1, dash: "dot" },
    },
  ];
}
