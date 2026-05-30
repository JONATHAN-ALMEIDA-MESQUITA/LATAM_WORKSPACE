import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Permite trocar a porta do backend via .env (VITE_API_TARGET).
// Default: http://127.0.0.1:8000.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
    },
    optimizeDeps: {
      // Força pre-bundling explícito + nome amigável.
      // react-plotly.js tem `.js` no nome e gera bug do dep optimizer no Vite v5.
      // Importamos via factory + plotly direto no código (ver WidgetRenderer).
      include: ["plotly.js-dist-min", "react-plotly.js/factory"],
    },
  };
});
