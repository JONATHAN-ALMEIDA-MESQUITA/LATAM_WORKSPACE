/**
 * AlertBuilder - editor dinamico de regra de alerta (modal).
 *
 * UI muda conforme alert_type:
 *   - metric_threshold  : metrica, operator, threshold, period, filters
 *   - metric_change     : metrica, current_period, prev_period, change_pct, direction
 *   - forecast_quality  : forecast, mape_threshold, scope
 *   - pipeline_failure  : pipeline, lookback_minutes
 *   - dashboard_stale   : dashboard, max_age_days
 */

import { useEffect, useMemo, useState } from "react";
import {
  DashboardsAPI,
  ForecastsAPI,
  MetricsAPI,
  PipelinesAPI,
} from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/store/authStore";
import type {
  Alert,
  AlertCreatePayload,
  AlertSeverity,
  AlertType,
  DashboardSummary,
  ForecastSummary,
  Metric,
  PipelineSummary,
} from "@/types";

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  metric_threshold: "Metric Threshold",
  metric_change: "Metric Change",
  forecast_quality: "Forecast Quality (MAPE)",
  pipeline_failure: "Pipeline Failure",
  dashboard_stale: "Dashboard Stale",
};

const ALERT_TYPE_DESC: Record<AlertType, string> = {
  metric_threshold:
    "Dispara quando uma metrica viola um threshold (ex: revenue MTD < 1M).",
  metric_change:
    "Dispara quando uma metrica varia mais que X% vs periodo anterior.",
  forecast_quality:
    "Dispara quando o MAPE de um forecast esta acima do limite (qualidade baixa).",
  pipeline_failure:
    "Dispara quando o ultimo run de um pipeline falhou recentemente.",
  dashboard_stale:
    "Dispara quando um dashboard publicado nao recebe update ha N dias.",
};

const SEVERITY_OPTIONS: { value: AlertSeverity; label: string }[] = [
  { value: "info", label: "Info" },
  { value: "warning", label: "Warning" },
  { value: "critical", label: "Critical" },
];

const PERIODS = [
  { value: "all", label: "Todos os periodos" },
  { value: "mtd", label: "Mes ate hoje (MTD)" },
  { value: "ytd", label: "Ano ate hoje (YTD)" },
  { value: "last_30d", label: "Ultimos 30 dias" },
  { value: "last_7d", label: "Ultimos 7 dias" },
];

const PREV_PERIODS = [
  { value: "prev_month", label: "Mes anterior" },
  { value: "prev_year", label: "Mesmo mes ano anterior" },
];

const OPERATORS = ["<", "<=", ">", ">=", "==", "!="];

interface Props {
  open: boolean;
  onClose: () => void;
  onSaved: (alert: Alert) => void;
  /** Se passado, edita; senao cria. */
  initialAlert?: Alert | null;
  defaultWorkspace: string;
  defaultBusinessArea?: string;
}

export function AlertBuilder({
  open,
  onClose,
  onSaved,
  initialAlert,
  defaultWorkspace,
  defaultBusinessArea = "",
}: Props) {
  const accessibleWorkspaces = useAuthStore((s) => s.menu?.workspaces ?? []);
  const isEdit = !!initialAlert;

  const [form, setForm] = useState<AlertCreatePayload>(() =>
    initialAlert
      ? {
          name: initialAlert.name,
          description: initialAlert.description,
          workspace: initialAlert.workspace,
          business_area: initialAlert.business_area,
          alert_type: initialAlert.alert_type,
          severity: initialAlert.severity,
          target_id: initialAlert.target_id,
          target_kind: initialAlert.target_kind,
          rule_config: initialAlert.rule_config,
          channels: initialAlert.channels,
          recipients: initialAlert.recipients,
          enabled: initialAlert.enabled,
          cooldown_minutes: initialAlert.cooldown_minutes,
        }
      : {
          name: "",
          description: "",
          workspace: defaultWorkspace,
          business_area: defaultBusinessArea,
          alert_type: "metric_threshold",
          severity: "warning",
          target_id: null,
          target_kind: "metric",
          rule_config: { operator: "<", threshold: 0, period: "all" },
          channels: ["in_app", "email"],
          recipients: [],
          enabled: true,
          cooldown_minutes: 60,
        },
  );

  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [forecasts, setForecasts] = useState<ForecastSummary[]>([]);
  const [pipelines, setPipelines] = useState<PipelineSummary[]>([]);
  const [dashboards, setDashboards] = useState<DashboardSummary[]>([]);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recipientInput, setRecipientInput] = useState((form.recipients ?? []).join(", "));

  // Carrega listas de targets quando o modal abrir
  useEffect(() => {
    if (!open) return;
    MetricsAPI.list().then(setMetrics).catch(() => setMetrics([]));
    ForecastsAPI.list().then(setForecasts).catch(() => setForecasts([]));
    PipelinesAPI.list().then(setPipelines).catch(() => setPipelines([]));
    DashboardsAPI.list().then(setDashboards).catch(() => setDashboards([]));
  }, [open]);

  // Quando trocar de tipo, define target_kind + rule_config base
  function handleTypeChange(t: AlertType) {
    const defaults: Record<AlertType, { kind: string; cfg: Record<string, unknown> }> = {
      metric_threshold: {
        kind: "metric",
        cfg: { operator: "<", threshold: 0, period: "all" },
      },
      metric_change: {
        kind: "metric",
        cfg: {
          change_pct_threshold: 10.0,
          direction: "drop",
          current_period: "mtd",
          previous_period: "prev_month",
        },
      },
      forecast_quality: {
        kind: "forecast",
        cfg: { mape_threshold: 25.0, scope: "any" },
      },
      pipeline_failure: {
        kind: "pipeline",
        cfg: { lookback_minutes: 1440 },
      },
      dashboard_stale: {
        kind: "dashboard",
        cfg: { max_age_days: 7 },
      },
    };
    const d = defaults[t];
    setForm({
      ...form,
      alert_type: t,
      target_kind: d.kind as Alert["target_kind"],
      target_id: null,
      rule_config: d.cfg,
    });
  }

  function setRule(patch: Record<string, unknown>) {
    setForm({ ...form, rule_config: { ...form.rule_config, ...patch } });
  }

  function toggleChannel(c: string) {
    const channels = form.channels ?? [];
    setForm({
      ...form,
      channels: channels.includes(c)
        ? channels.filter((x) => x !== c)
        : [...channels, c],
    });
  }

  const filteredMetrics = useMemo(
    () => metrics.filter((m) => !form.workspace || m.workspace === form.workspace),
    [metrics, form.workspace],
  );
  const filteredForecasts = useMemo(
    () => forecasts.filter((f) => !form.workspace || f.workspace === form.workspace),
    [forecasts, form.workspace],
  );
  const filteredPipelines = useMemo(
    () => pipelines.filter((p) => !form.workspace || p.workspace === form.workspace),
    [pipelines, form.workspace],
  );
  const filteredDashboards = useMemo(
    () => dashboards.filter((d) => !form.workspace || d.workspace === form.workspace),
    [dashboards, form.workspace],
  );

  async function handleSave() {
    setError(null);
    if (!form.name || form.name.length < 2) {
      setError("Nome obrigatorio.");
      return;
    }
    if (!form.target_id) {
      setError("Selecione um target (metric/forecast/pipeline/dashboard).");
      return;
    }
    const recipients = recipientInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const payload: AlertCreatePayload = { ...form, recipients };
    setSaving(true);
    try {
      const { AlertsAPI } = await import("@/api/client");
      const saved = isEdit
        ? await AlertsAPI.update(initialAlert!.id, payload)
        : await AlertsAPI.create(payload);
      onSaved(saved);
      onClose();
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          "Falha ao salvar.",
      );
    } finally {
      setSaving(false);
    }
  }

  const rule = (form.rule_config ?? {}) as Record<string, unknown>;

  return (
    <Modal
      open={open}
      title={isEdit ? `Editar alerta - ${initialAlert?.name}` : "Novo alerta"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button variant="primary" onClick={handleSave} disabled={saving}>
            {saving ? "Salvando..." : isEdit ? "Salvar" : "Criar"}
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-xs">
        {error && (
          <div className="rounded border border-rose-200 bg-rose-50 p-2 text-rose-700">{error}</div>
        )}

        <div>
          <label className="font-semibold text-slate-600">Nome *</label>
          <input
            className="input"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Ex: Revenue YTD abaixo de 5M"
          />
        </div>

        <div>
          <label className="font-semibold text-slate-600">Descricao</label>
          <textarea
            className="input min-h-[50px]"
            value={form.description ?? ""}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="font-semibold text-slate-600">Workspace *</label>
            <select
              className="input"
              value={form.workspace}
              onChange={(e) => setForm({ ...form, workspace: e.target.value })}
            >
              {accessibleWorkspaces.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="font-semibold text-slate-600">Severidade *</label>
            <select
              className="input"
              value={form.severity}
              onChange={(e) =>
                setForm({ ...form, severity: e.target.value as AlertSeverity })
              }
            >
              {SEVERITY_OPTIONS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="rounded border border-brand-200 bg-brand-50 p-3">
          <label className="font-semibold text-slate-700">Tipo de regra *</label>
          <select
            className="input mt-1"
            value={form.alert_type}
            onChange={(e) => handleTypeChange(e.target.value as AlertType)}
            disabled={isEdit}
          >
            {Object.entries(ALERT_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <div className="mt-1 text-[11px] text-slate-600">
            {ALERT_TYPE_DESC[form.alert_type]}
          </div>
        </div>

        {/* === UI dinamica por tipo === */}
        {form.alert_type === "metric_threshold" && (
          <div className="space-y-2 rounded border border-slate-200 p-3">
            <div>
              <label className="font-semibold text-slate-600">Metrica *</label>
              <select
                className="input"
                value={form.target_id ?? ""}
                onChange={(e) =>
                  setForm({ ...form, target_id: Number(e.target.value) || null })
                }
              >
                <option value="">Selecione...</option>
                {filteredMetrics.map((m) => (
                  <option key={m.id} value={m.id}>
                    #{m.id} {m.name} ({m.business_area})
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="font-semibold text-slate-600">Operador</label>
                <select
                  className="input"
                  value={String(rule.operator ?? "<")}
                  onChange={(e) => setRule({ operator: e.target.value })}
                >
                  {OPERATORS.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-semibold text-slate-600">Threshold</label>
                <input
                  type="number"
                  step="any"
                  className="input"
                  value={Number(rule.threshold ?? 0)}
                  onChange={(e) => setRule({ threshold: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="font-semibold text-slate-600">Periodo</label>
                <select
                  className="input"
                  value={String(rule.period ?? "all")}
                  onChange={(e) => setRule({ period: e.target.value })}
                >
                  {PERIODS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="text-[10px] text-slate-500">
              Para periodos !== "all", a metrica precisa ter <code>date_column</code> definida.
            </div>
          </div>
        )}

        {form.alert_type === "metric_change" && (
          <div className="space-y-2 rounded border border-slate-200 p-3">
            <div>
              <label className="font-semibold text-slate-600">Metrica *</label>
              <select
                className="input"
                value={form.target_id ?? ""}
                onChange={(e) =>
                  setForm({ ...form, target_id: Number(e.target.value) || null })
                }
              >
                <option value="">Selecione...</option>
                {filteredMetrics.map((m) => (
                  <option key={m.id} value={m.id}>
                    #{m.id} {m.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="font-semibold text-slate-600">Direcao</label>
                <select
                  className="input"
                  value={String(rule.direction ?? "drop")}
                  onChange={(e) => setRule({ direction: e.target.value })}
                >
                  <option value="drop">Queda</option>
                  <option value="raise">Subida</option>
                  <option value="any">Qualquer</option>
                </select>
              </div>
              <div>
                <label className="font-semibold text-slate-600">Threshold %</label>
                <input
                  type="number"
                  step="any"
                  className="input"
                  value={Number(rule.change_pct_threshold ?? 10)}
                  onChange={(e) =>
                    setRule({ change_pct_threshold: Number(e.target.value) })
                  }
                />
              </div>
              <div>
                <label className="font-semibold text-slate-600">date_column</label>
                <input
                  className="input"
                  value={String(rule.date_column ?? "date")}
                  onChange={(e) => setRule({ date_column: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="font-semibold text-slate-600">Periodo atual</label>
                <select
                  className="input"
                  value={String(rule.current_period ?? "mtd")}
                  onChange={(e) => setRule({ current_period: e.target.value })}
                >
                  {PERIODS.filter((p) => p.value !== "all").map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="font-semibold text-slate-600">Periodo anterior</label>
                <select
                  className="input"
                  value={String(rule.previous_period ?? "prev_month")}
                  onChange={(e) => setRule({ previous_period: e.target.value })}
                >
                  {PREV_PERIODS.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}

        {form.alert_type === "forecast_quality" && (
          <div className="space-y-2 rounded border border-slate-200 p-3">
            <div>
              <label className="font-semibold text-slate-600">Forecast *</label>
              <select
                className="input"
                value={form.target_id ?? ""}
                onChange={(e) =>
                  setForm({ ...form, target_id: Number(e.target.value) || null })
                }
              >
                <option value="">Selecione...</option>
                {filteredForecasts.map((f) => (
                  <option key={f.id} value={f.id}>
                    #{f.id} {f.name} ({f.algorithm})
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="font-semibold text-slate-600">MAPE threshold (%)</label>
                <input
                  type="number"
                  step="any"
                  className="input"
                  value={Number(rule.mape_threshold ?? 25)}
                  onChange={(e) => setRule({ mape_threshold: Number(e.target.value) })}
                />
              </div>
              <div>
                <label className="font-semibold text-slate-600">Escopo</label>
                <select
                  className="input"
                  value={String(rule.scope ?? "any")}
                  onChange={(e) => setRule({ scope: e.target.value })}
                >
                  <option value="any">Qualquer grupo (max)</option>
                  <option value="all">Todos os grupos (min)</option>
                  <option value="average">Media</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {form.alert_type === "pipeline_failure" && (
          <div className="space-y-2 rounded border border-slate-200 p-3">
            <div>
              <label className="font-semibold text-slate-600">Pipeline *</label>
              <select
                className="input"
                value={form.target_id ?? ""}
                onChange={(e) =>
                  setForm({ ...form, target_id: Number(e.target.value) || null })
                }
              >
                <option value="">Selecione...</option>
                {filteredPipelines.map((p) => (
                  <option key={p.id} value={p.id}>
                    #{p.id} {p.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="font-semibold text-slate-600">
                Lookback (minutos) - so dispara se a falha ocorreu nesse intervalo
              </label>
              <input
                type="number"
                className="input"
                value={Number(rule.lookback_minutes ?? 1440)}
                onChange={(e) => setRule({ lookback_minutes: Number(e.target.value) })}
              />
            </div>
          </div>
        )}

        {form.alert_type === "dashboard_stale" && (
          <div className="space-y-2 rounded border border-slate-200 p-3">
            <div>
              <label className="font-semibold text-slate-600">Dashboard *</label>
              <select
                className="input"
                value={form.target_id ?? ""}
                onChange={(e) =>
                  setForm({ ...form, target_id: Number(e.target.value) || null })
                }
              >
                <option value="">Selecione...</option>
                {filteredDashboards.map((d) => (
                  <option key={d.id} value={d.id}>
                    #{d.id} {d.name} ({d.status})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="font-semibold text-slate-600">Max age (dias)</label>
              <input
                type="number"
                className="input"
                value={Number(rule.max_age_days ?? 7)}
                onChange={(e) => setRule({ max_age_days: Number(e.target.value) })}
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="font-semibold text-slate-600">Cooldown (minutos)</label>
            <input
              type="number"
              className="input"
              value={form.cooldown_minutes ?? 60}
              onChange={(e) =>
                setForm({ ...form, cooldown_minutes: Number(e.target.value) })
              }
            />
            <div className="text-[10px] text-slate-500">
              Tempo minimo entre disparos consecutivos.
            </div>
          </div>
          <div>
            <label className="font-semibold text-slate-600">Canais</label>
            <div className="mt-1 flex gap-3 text-[11px]">
              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={form.channels?.includes("in_app") ?? false}
                  onChange={() => toggleChannel("in_app")}
                />
                In-App
              </label>
              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={form.channels?.includes("email") ?? false}
                  onChange={() => toggleChannel("email")}
                />
                E-mail (mock)
              </label>
              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={form.channels?.includes("slack") ?? false}
                  onChange={() => toggleChannel("slack")}
                />
                Slack (mock)
              </label>
              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={form.channels?.includes("teams") ?? false}
                  onChange={() => toggleChannel("teams")}
                />
                Teams (mock)
              </label>
            </div>
          </div>
        </div>

        <div>
          <label className="font-semibold text-slate-600">
            Destinatarios (e-mails, separados por virgula)
          </label>
          <input
            className="input"
            value={recipientInput}
            onChange={(e) => setRecipientInput(e.target.value)}
            placeholder="Vazio = enviar para o criador"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            id="enabled"
            type="checkbox"
            checked={form.enabled ?? true}
            onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
          />
          <label htmlFor="enabled" className="text-xs font-semibold text-slate-600">
            Habilitado
          </label>
        </div>
      </div>
    </Modal>
  );
}
