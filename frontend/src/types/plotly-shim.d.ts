// Shim de tipos: plotly.js-dist-min e react-plotly.js/factory não trazem
// declarações úteis. Usamos `any` aqui para evitar lock no TS strict;
// a tipagem correta vem do uso (Plot recebe data/layout/style/config).

declare module "plotly.js-dist-min" {
  const Plotly: any;
  export default Plotly;
}

declare module "react-plotly.js/factory" {
  import type { ComponentType } from "react";
  interface PlotProps {
    data?: unknown;
    layout?: unknown;
    config?: unknown;
    style?: React.CSSProperties;
    useResizeHandler?: boolean;
    className?: string;
    onInitialized?: (figure: unknown, graphDiv: HTMLDivElement) => void;
    onUpdate?: (figure: unknown, graphDiv: HTMLDivElement) => void;
  }
  export default function createPlotlyComponent(plotly: unknown): ComponentType<PlotProps>;
}
