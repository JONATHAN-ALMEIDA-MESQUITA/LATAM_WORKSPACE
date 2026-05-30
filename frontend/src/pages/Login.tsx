import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthAPI } from "@/api/client";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useAuthStore } from "@/store/authStore";
import type { DemoUser } from "@/types";

const roleTone: Record<string, "brand" | "info" | "success" | "warning" | "neutral" | "danger"> = {
  "Platform Admin": "danger",
  "Data Developer": "brand",
  "Data Analyst Brazil": "info",
  "Data Analyst": "info",
  "Finance Owner": "success",
  "Operations Owner": "warning",
  "LATAM Executive Viewer": "brand",
  Viewer: "neutral",
  "ML Owner": "info",
};

export default function LoginPage() {
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const login = useAuthStore((s) => s.login);
  const loginLoading = useAuthStore((s) => s.isLoading);
  const loginError = useAuthStore((s) => s.error);
  const token = useAuthStore((s) => s.token);
  const navigate = useNavigate();

  useEffect(() => {
    if (token) navigate("/", { replace: true });
  }, [token, navigate]);

  useEffect(() => {
    let mounted = true;
    AuthAPI.listDemoUsers()
      .then((list) => {
        if (!mounted) return;
        setDemoUsers(list);
        if (list.length > 0) setSelected(list[0].email);
      })
      .catch((err) => {
        if (!mounted) return;
        setLoadError(
          err?.message?.includes("Network")
            ? "Não consegui falar com o backend. Confirme que o FastAPI está rodando em http://127.0.0.1:8000."
            : "Falha ao carregar usuários da demo.",
        );
      })
      .finally(() => mounted && setLoadingList(false));
    return () => {
      mounted = false;
    };
  }, []);

  async function handleLogin() {
    if (!selected) return;
    try {
      await login(selected);
      navigate("/", { replace: true });
    } catch {
      // erro já vai pro store
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-ink-50">
      {/* Coluna esquerda - branding */}
      <div className="hidden lg:flex flex-col justify-between bg-gradient-to-br from-brand-700 via-brand-800 to-ink-900 p-12 text-white">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center font-bold">
              L
            </div>
            <div className="text-xl font-semibold tracking-tight">LATAM Analytics</div>
          </div>
          <h1 className="mt-16 text-4xl font-bold leading-tight">
            Self-service BI <br /> para times de dados, finanças e operações.
          </h1>
          <p className="mt-4 text-brand-100 text-lg max-w-md">
            Builder Studio para criar. Business Portal para consumir. Tudo em
            um único lugar, com governança e RBAC.
          </p>
        </div>
        <div className="space-y-3 text-sm text-brand-100">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            ETL visual por blocos + Pandas/DuckDB
          </div>
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Dashboards drag-and-drop com camada semântica
          </div>
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Forecasting + Scheduler + Audit Trail
          </div>
        </div>
      </div>

      {/* Coluna direita - escolha de perfil */}
      <div className="flex items-center justify-center p-6 sm:p-12">
        <div className="w-full max-w-xl">
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-brand-600 text-white flex items-center justify-center font-bold">
              L
            </div>
            <div className="text-xl font-semibold tracking-tight text-ink-900">
              LATAM Analytics
            </div>
          </div>

          <h2 className="text-2xl font-bold text-ink-900">Entrar na plataforma</h2>
          <p className="mt-1 text-sm text-ink-500">
            Demo com login simulado. Escolha um perfil para continuar.
          </p>

          {loadError && (
            <div className="mt-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {loadError}
            </div>
          )}
          {loginError && !loadError && (
            <div className="mt-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {loginError}
            </div>
          )}

          <div className="mt-6 space-y-2">
            {loadingList && (
              <div className="space-y-2">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    className="h-16 rounded-xl border border-ink-200 bg-white animate-pulse"
                  />
                ))}
              </div>
            )}

            {!loadingList &&
              demoUsers.map((u) => {
                const isActive = selected === u.email;
                return (
                  <button
                    key={u.email}
                    onClick={() => setSelected(u.email)}
                    className={[
                      "w-full text-left rounded-xl border bg-white px-4 py-3 transition-all",
                      "hover:border-brand-400 hover:shadow-soft",
                      isActive
                        ? "border-brand-500 ring-2 ring-brand-100"
                        : "border-ink-200",
                    ].join(" ")}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-ink-900 truncate">
                            {u.full_name}
                          </span>
                          <Badge tone={roleTone[u.role] ?? "neutral"}>{u.role}</Badge>
                        </div>
                        <div className="mt-0.5 text-xs text-ink-500 truncate">
                          {u.email} · workspace: {u.home_workspace}
                        </div>
                      </div>
                      <div
                        className={[
                          "h-5 w-5 rounded-full border-2 flex items-center justify-center",
                          isActive ? "border-brand-600 bg-brand-600" : "border-ink-300",
                        ].join(" ")}
                      >
                        {isActive && (
                          <span className="h-2 w-2 rounded-full bg-white" />
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
          </div>

          <div className="mt-6 flex items-center justify-between gap-3">
            <p className="text-xs text-ink-500">
              Sem senha. Login simulado apenas para a demo.
            </p>
            <Button
              onClick={handleLogin}
              disabled={!selected || loadingList}
              loading={loginLoading}
            >
              Entrar como selecionado
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
