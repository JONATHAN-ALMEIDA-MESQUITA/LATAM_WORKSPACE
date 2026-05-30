import axios from "axios";
import type {
  Alert,
  AlertCreatePayload,
  AlertEvaluationResult,
  AlertUpdatePayload,
  Dashboard,
  DashboardCreatePayload,
  DashboardSummary,
  Dataset,
  DatasetColumn,
  DatasetPreview,
  DatasetSummary,
  DataSource,
  DataSourceCreatePayload,
  DemoUser,
  EvaluateAllResponse,
  ForecastCreatePayload,
  ForecastDetail,
  ForecastRun,
  ForecastSummary,
  ForecastTrainResponse,
  ForecastUpdatePayload,
  LoginResponse,
  Notification,
  NotificationSummary,
  Metric,
  MetricCreatePayload,
  MetricPreviewPayload,
  MetricPreviewResult,
  Pipeline,
  PipelineCreatePayload,
  PipelinePreviewPayload,
  PipelinePreviewResult,
  PipelineRun,
  PipelineStep,
  PipelineSummary,
  SampleCatalogItem,
  ScheduledJob,
  ScheduledJobCreatePayload,
  ScheduledJobRun,
  ScheduledJobUpdatePayload,
  SchedulerStatus,
  ReportExample,
  ReportExportPayload,
  ReportPreviewPayload,
  ReportPreviewResult,
  ReportSaveDatasetPayload,
  ReportSaveDatasetResult,
  JoinSuggestion,
  ExtraDatasetRef,
  VisualReportPayload,
  SavedReport,
  SavedReportCreatePayload,
  SavedReportUpdatePayload,
  StepCreatePayload,
  StepUpdatePayload,
  TestConnectionResult,
  User,
  UserCreatePayload,
  UserUpdatePayload,
  AuditLogEntry,
  PermissionsMatrix,
  SystemStatus,
  DatasetLineage,
  DatasetQuality,
  RegisteredModel,
  RegisteredModelCreatePayload,
  WorkspaceUpdatePayload,
  Widget,
  WidgetLayout,
  WidgetPreviewPayload,
  WidgetRenderResult,
  Workspace,
} from "@/types";

// Em dev, Vite faz proxy: /api -> http://127.0.0.1:8000
export const api = axios.create({
  baseURL: "/api",
  timeout: 15_000,
});

// Interceptor de Authorization - lê token salvo pelo authStore.
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("latam.token");
  if (token) {
    cfg.headers = cfg.headers ?? {};
    cfg.headers.Authorization = `Bearer ${token}`;
  }
  return cfg;
});

// Interceptor de erro - redireciona para login em 401.
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem("latam.token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export const AuthAPI = {
  listDemoUsers: () => api.get<DemoUser[]>("/auth/users-demo").then((r) => r.data),
  login: (email: string) =>
    api.post<LoginResponse>("/auth/login", { email }).then((r) => r.data),
  me: () => api.get<LoginResponse>("/auth/me").then((r) => r.data),
};

export const WorkspacesAPI = {
  list: () => api.get<Workspace[]>("/workspaces").then((r) => r.data),
  listAll: () => api.get<Workspace[]>("/workspaces/all").then((r) => r.data),
  update: (id: number, payload: WorkspaceUpdatePayload) =>
    api.put<Workspace>(`/workspaces/${id}`, payload).then((r) => r.data),
};

export const DatasetsAPI = {
  list: (params?: {
    workspace?: string;
    business_area?: string;
    status_filter?: string;
  }) =>
    api
      .get<DatasetSummary[]>("/datasets", { params })
      .then((r) => r.data),

  get: (id: number) => api.get<Dataset>(`/datasets/${id}`).then((r) => r.data),

  preview: (id: number, limit = 100) =>
    api
      .get<DatasetPreview>(`/datasets/${id}/preview`, { params: { limit } })
      .then((r) => r.data),

  profile: (id: number) =>
    api.get<DatasetColumn[]>(`/datasets/${id}/profile`).then((r) => r.data),

  upload: (
    file: File,
    options: {
      dataset_name: string;
      description?: string;
      workspace?: string;
      business_area?: string;
      onProgress?: (pct: number) => void;
    },
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("dataset_name", options.dataset_name);
    form.append("description", options.description ?? "");
    form.append("workspace", options.workspace ?? "LATAM");
    form.append("business_area", options.business_area ?? "");
    return api
      .post<Dataset>("/datasets/upload", form, {
        onUploadProgress: (e) => {
          if (e.total && options.onProgress) {
            options.onProgress(Math.round((e.loaded * 100) / e.total));
          }
        },
      })
      .then((r) => r.data);
  },

  listSamples: () =>
    api.get<SampleCatalogItem[]>("/datasets/samples").then((r) => r.data),

  generateSample: (name: string, workspace = "LATAM") =>
    api
      .post<Dataset>("/datasets/sample", { name, workspace })
      .then((r) => r.data),

  generateAllSamples: (force = false) =>
    api
      .post<DatasetSummary[]>(`/datasets/samples/all?force=${force}`)
      .then((r) => r.data),

  changeStatus: (id: number, newStatus: string) =>
    api
      .post<Dataset>(`/datasets/${id}/status`, { status: newStatus })
      .then((r) => r.data),

  lineage: (id: number) =>
    api.get<DatasetLineage>(`/datasets/${id}/lineage`).then((r) => r.data),

  quality: (id: number) =>
    api.get<DatasetQuality>(`/datasets/${id}/quality`).then((r) => r.data),

  runQuality: (id: number) =>
    api.post<DatasetQuality>(`/datasets/${id}/quality/run`).then((r) => r.data),

  delete: (id: number) => api.delete(`/datasets/${id}`).then((r) => r.data),
};

export const DataSourcesAPI = {
  list: () => api.get<DataSource[]>("/data-sources").then((r) => r.data),
  create: (payload: DataSourceCreatePayload) =>
    api.post<DataSource>("/data-sources", payload).then((r) => r.data),
  update: (id: number, payload: Partial<DataSourceCreatePayload> & { status?: string }) =>
    api.put<DataSource>(`/data-sources/${id}`, payload).then((r) => r.data),
  delete: (id: number) => api.delete(`/data-sources/${id}`).then((r) => r.data),
  test: (id: number) =>
    api.post<TestConnectionResult>(`/data-sources/${id}/test`).then((r) => r.data),
};

export const MetricsAPI = {
  list: (params?: { dataset_id?: number; workspace?: string; business_area?: string; status?: string }) =>
    api.get<Metric[]>("/metrics", { params }).then((r) => r.data),
  get: (id: number) => api.get<Metric>(`/metrics/${id}`).then((r) => r.data),
  create: (payload: MetricCreatePayload) =>
    api.post<Metric>("/metrics", payload).then((r) => r.data),
  update: (id: number, payload: Partial<MetricCreatePayload> & { status?: string }) =>
    api.put<Metric>(`/metrics/${id}`, payload).then((r) => r.data),
  delete: (id: number) => api.delete(`/metrics/${id}`).then((r) => r.data),
  preview: (payload: MetricPreviewPayload) =>
    api.post<MetricPreviewResult>("/metrics/preview", payload).then((r) => r.data),
};

export const DashboardsAPI = {
  list: (params?: { workspace?: string; business_area?: string; status?: string }) =>
    api.get<DashboardSummary[]>("/dashboards", { params }).then((r) => r.data),
  listPublished: (params?: { workspace?: string; business_area?: string }) =>
    api.get<DashboardSummary[]>("/dashboards/published", { params }).then((r) => r.data),
  get: (id: number) => api.get<Dashboard>(`/dashboards/${id}`).then((r) => r.data),
  create: (payload: DashboardCreatePayload) =>
    api.post<Dashboard>("/dashboards", payload).then((r) => r.data),
  update: (id: number, payload: Partial<DashboardCreatePayload>) =>
    api.put<Dashboard>(`/dashboards/${id}`, payload).then((r) => r.data),
  delete: (id: number) => api.delete(`/dashboards/${id}`).then((r) => r.data),
  render: (id: number) =>
    api.post<WidgetRenderResult[]>(`/dashboards/${id}/render`).then((r) => r.data),

  // Widgets
  createWidget: (dashboardId: number, payload: {
    title?: string;
    widget_type: string;
    layout?: WidgetLayout;
    config?: Record<string, unknown>;
  }) =>
    api.post<Widget>(`/dashboards/${dashboardId}/widgets`, payload).then((r) => r.data),
  updateWidget: (dashboardId: number, widgetId: number, payload: {
    title?: string;
    widget_type?: string;
    layout?: WidgetLayout;
    config?: Record<string, unknown>;
  }) =>
    api
      .put<Widget>(`/dashboards/${dashboardId}/widgets/${widgetId}`, payload)
      .then((r) => r.data),
  deleteWidget: (dashboardId: number, widgetId: number) =>
    api.delete(`/dashboards/${dashboardId}/widgets/${widgetId}`).then((r) => r.data),

  // Widget preview ad-hoc (Dashboard Builder)
  previewWidget: (payload: WidgetPreviewPayload) =>
    api.post<WidgetRenderResult>("/dashboards/widgets/preview", payload).then((r) => r.data),

  // Publish flow
  submit: (id: number, comment = "") =>
    api.post<Dashboard>(`/dashboards/${id}/submit`, { comment }).then((r) => r.data),
  publish: (id: number, comment = "") =>
    api.post<Dashboard>(`/dashboards/${id}/publish`, { comment }).then((r) => r.data),
  archive: (id: number, comment = "") =>
    api.post<Dashboard>(`/dashboards/${id}/archive`, { comment }).then((r) => r.data),
  reject: (id: number, comment = "") =>
    api.post<Dashboard>(`/dashboards/${id}/reject`, { comment }).then((r) => r.data),

  exportPdf: async (id: number) => {
    const res = await api.post(`/dashboards/${id}/export-pdf`, null, { responseType: "blob" });
    const blob = new Blob([res.data], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const cd = res.headers["content-disposition"] as string | undefined;
    const match = cd?.match(/filename="(.+?)"/);
    a.download = match?.[1] ?? `dashboard-${id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export const PipelinesAPI = {
  list: (params?: { workspace?: string; business_area?: string; status?: string }) =>
    api.get<PipelineSummary[]>("/pipelines", { params }).then((r) => r.data),
  get: (id: number) => api.get<Pipeline>(`/pipelines/${id}`).then((r) => r.data),
  create: (payload: PipelineCreatePayload) =>
    api.post<Pipeline>("/pipelines", payload).then((r) => r.data),
  update: (id: number, payload: Partial<PipelineCreatePayload>) =>
    api.put<Pipeline>(`/pipelines/${id}`, payload).then((r) => r.data),
  delete: (id: number) => api.delete(`/pipelines/${id}`).then((r) => r.data),

  // Steps
  createStep: (pipelineId: number, payload: StepCreatePayload) =>
    api.post<PipelineStep>(`/pipelines/${pipelineId}/steps`, payload).then((r) => r.data),
  updateStep: (pipelineId: number, stepId: number, payload: StepUpdatePayload) =>
    api
      .put<PipelineStep>(`/pipelines/${pipelineId}/steps/${stepId}`, payload)
      .then((r) => r.data),
  deleteStep: (pipelineId: number, stepId: number) =>
    api.delete(`/pipelines/${pipelineId}/steps/${stepId}`).then((r) => r.data),
  reorderSteps: (pipelineId: number, stepIds: number[]) =>
    api
      .post<PipelineStep[]>(`/pipelines/${pipelineId}/steps/reorder`, { step_ids: stepIds })
      .then((r) => r.data),

  // Preview
  previewAdhoc: (payload: PipelinePreviewPayload) =>
    api.post<PipelinePreviewResult>("/pipelines/preview", payload).then((r) => r.data),
  preview: (pipelineId: number, payload: PipelinePreviewPayload) =>
    api
      .post<PipelinePreviewResult>(`/pipelines/${pipelineId}/preview`, payload)
      .then((r) => r.data),

  // Run + history
  run: (pipelineId: number, note = "") =>
    api.post<PipelineRun>(`/pipelines/${pipelineId}/run`, { note }).then((r) => r.data),
  runs: (pipelineId: number, limit = 50) =>
    api
      .get<PipelineRun[]>(`/pipelines/${pipelineId}/runs`, { params: { limit } })
      .then((r) => r.data),

  // Publish flow
  publish: (id: number, note = "") =>
    api.post<Pipeline>(`/pipelines/${id}/publish`, { note }).then((r) => r.data),
  archive: (id: number, note = "") =>
    api.post<Pipeline>(`/pipelines/${id}/archive`, { note }).then((r) => r.data),
};

// =====================
// Forecasts (Phase 4)
// =====================
export const ForecastsAPI = {
  list: (params?: { workspace?: string; business_area?: string; status?: string }) =>
    api.get<ForecastSummary[]>("/forecasts", { params }).then((r) => r.data),
  get: (id: number) => api.get<ForecastDetail>(`/forecasts/${id}`).then((r) => r.data),
  create: (payload: ForecastCreatePayload) =>
    api.post<ForecastDetail>("/forecasts", payload).then((r) => r.data),
  update: (id: number, payload: ForecastUpdatePayload) =>
    api.put<ForecastDetail>(`/forecasts/${id}`, payload).then((r) => r.data),
  delete: (id: number) => api.delete(`/forecasts/${id}`).then((r) => r.data),
  train: (id: number) =>
    api.post<ForecastTrainResponse>(`/forecasts/${id}/train`).then((r) => r.data),
  publish: (id: number, note = "") =>
    api.post<ForecastDetail>(`/forecasts/${id}/publish`, { note }).then((r) => r.data),
  archive: (id: number, note = "") =>
    api.post<ForecastDetail>(`/forecasts/${id}/archive`, { note }).then((r) => r.data),
  runs: (id: number, limit = 50) =>
    api.get<ForecastRun[]>(`/forecasts/${id}/runs`, { params: { limit } }).then((r) => r.data),
};

// =====================
// Alerts & Notifications (Phase 5)
// =====================
export const AlertsAPI = {
  list: (params?: {
    workspace?: string;
    business_area?: string;
    alert_type?: string;
    severity?: string;
    enabled?: boolean;
  }) => api.get<Alert[]>("/alerts", { params }).then((r) => r.data),
  get: (id: number) => api.get<Alert>(`/alerts/${id}`).then((r) => r.data),
  create: (payload: AlertCreatePayload) =>
    api.post<Alert>("/alerts", payload).then((r) => r.data),
  update: (id: number, payload: AlertUpdatePayload) =>
    api.put<Alert>(`/alerts/${id}`, payload).then((r) => r.data),
  delete: (id: number) => api.delete(`/alerts/${id}`).then((r) => r.data),
  toggle: (id: number) => api.post<Alert>(`/alerts/${id}/toggle`).then((r) => r.data),
  evaluate: (id: number) =>
    api.post<AlertEvaluationResult>(`/alerts/${id}/evaluate`).then((r) => r.data),
  test: (id: number) =>
    api.post<AlertEvaluationResult>(`/alerts/${id}/test`).then((r) => r.data),
  evaluateAll: (workspace?: string) =>
    api
      .post<EvaluateAllResponse>("/alerts/evaluate-all", null, { params: { workspace } })
      .then((r) => r.data),
};

export const NotificationsAPI = {
  list: (params?: {
    status?: string;
    severity?: string;
    alert_type?: string;
    workspace?: string;
    limit?: number;
  }) => api.get<Notification[]>("/notifications", { params }).then((r) => r.data),
  summary: () => api.get<NotificationSummary>("/notifications/summary").then((r) => r.data),
  markRead: (id: number) =>
    api.post<Notification>(`/notifications/${id}/read`).then((r) => r.data),
  acknowledge: (id: number, note = "") =>
    api
      .post<Notification>(`/notifications/${id}/ack`, { note })
      .then((r) => r.data),
  markAllRead: () =>
    api.post<{ updated: number }>("/notifications/read-all").then((r) => r.data),
};

// =====================
// Scheduler (Phase 6)
// =====================
export const ScheduledJobsAPI = {
  list: (params?: { workspace?: string; job_type?: string; enabled?: boolean }) =>
    api.get<ScheduledJob[]>("/scheduled-jobs", { params }).then((r) => r.data),
  status: () => api.get<SchedulerStatus>("/scheduled-jobs/status").then((r) => r.data),
  get: (id: number) => api.get<ScheduledJob>(`/scheduled-jobs/${id}`).then((r) => r.data),
  create: (payload: ScheduledJobCreatePayload) =>
    api.post<ScheduledJob>("/scheduled-jobs", payload).then((r) => r.data),
  update: (id: number, payload: ScheduledJobUpdatePayload) =>
    api.put<ScheduledJob>(`/scheduled-jobs/${id}`, payload).then((r) => r.data),
  delete: (id: number) => api.delete(`/scheduled-jobs/${id}`).then((r) => r.data),
  pause: (id: number) =>
    api.post<ScheduledJob>(`/scheduled-jobs/${id}/pause`).then((r) => r.data),
  resume: (id: number) =>
    api.post<ScheduledJob>(`/scheduled-jobs/${id}/resume`).then((r) => r.data),
  runNow: (id: number) =>
    api.post<ScheduledJobRun>(`/scheduled-jobs/${id}/run-now`).then((r) => r.data),
  runs: (id: number, limit = 50) =>
    api
      .get<ScheduledJobRun[]>(`/scheduled-jobs/${id}/runs`, { params: { limit } })
      .then((r) => r.data),
};

// =====================
// Ad-Hoc Reports (Phase 7)
// =====================
export const ReportsAPI = {
  examples: (params?: { dataset_id?: number; extra_dataset_ids?: string }) =>
    api.get<ReportExample[]>("/reports/examples", { params }).then((r) => r.data),
  joinSuggestions: (datasetIds: number[]) =>
    api
      .get<JoinSuggestion[]>("/reports/join-suggestions", {
        params: { dataset_ids: datasetIds.join(",") },
      })
      .then((r) => r.data),
  preview: (payload: ReportPreviewPayload) =>
    api.post<ReportPreviewResult>("/reports/preview", payload).then((r) => r.data),
  visualPreview: (payload: VisualReportPayload) =>
    api.post<ReportPreviewResult>("/reports/visual-preview", payload).then((r) => r.data),
  exportCsv: async (payload: ReportExportPayload) => {
    const res = await api.post("/reports/export-csv", payload, { responseType: "blob" });
    const blob = new Blob([res.data], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const cd = res.headers["content-disposition"] as string | undefined;
    const match = cd?.match(/filename="(.+?)"/);
    a.download = match?.[1] ?? "report.csv";
    a.click();
    URL.revokeObjectURL(url);
  },
  saveDataset: (payload: ReportSaveDatasetPayload) =>
    api.post<ReportSaveDatasetResult>("/reports/save-dataset", payload).then((r) => r.data),
  listSaved: (params?: { workspace?: string }) =>
    api.get<SavedReport[]>("/reports/saved", { params }).then((r) => r.data),
  getSaved: (id: number) => api.get<SavedReport>(`/reports/saved/${id}`).then((r) => r.data),
  createSaved: (payload: SavedReportCreatePayload) =>
    api.post<SavedReport>("/reports/saved", payload).then((r) => r.data),
  updateSaved: (id: number, payload: SavedReportUpdatePayload) =>
    api.put<SavedReport>(`/reports/saved/${id}`, payload).then((r) => r.data),
  deleteSaved: (id: number) => api.delete(`/reports/saved/${id}`).then((r) => r.data),
  runSaved: (id: number, limit = 200) =>
    api
      .post<ReportPreviewResult>(`/reports/saved/${id}/run`, null, { params: { limit } })
      .then((r) => r.data),
};

// =====================
// Phase 9 — Extras
// =====================
export const ModelRegistryAPI = {
  list: (params?: { workspace?: string; status?: string }) =>
    api.get<RegisteredModel[]>("/model-registry", { params }).then((r) => r.data),
  register: (payload: RegisteredModelCreatePayload) =>
    api.post<RegisteredModel>("/model-registry", payload).then((r) => r.data),
  update: (id: number, payload: Partial<RegisteredModelCreatePayload> & { status?: string }) =>
    api.put<RegisteredModel>(`/model-registry/${id}`, payload).then((r) => r.data),
  promote: (id: number) =>
    api.post<RegisteredModel>(`/model-registry/${id}/promote`).then((r) => r.data),
};

// =====================
// Admin (Phase 8)
// =====================
export const UsersAPI = {
  list: () => api.get<User[]>("/users").then((r) => r.data),
  create: (payload: UserCreatePayload) =>
    api.post<User>("/users", payload).then((r) => r.data),
  update: (id: number, payload: UserUpdatePayload) =>
    api.put<User>(`/users/${id}`, payload).then((r) => r.data),
};

export const AdminAPI = {
  auditLogs: (params?: {
    user_email?: string;
    action?: string;
    workspace?: string;
    object_type?: string;
    limit?: number;
  }) => api.get<AuditLogEntry[]>("/admin/audit-logs", { params }).then((r) => r.data),
  permissionsMatrix: () =>
    api.get<PermissionsMatrix>("/admin/permissions/matrix").then((r) => r.data),
  systemStatus: () => api.get<SystemStatus>("/admin/system-status").then((r) => r.data),
};
