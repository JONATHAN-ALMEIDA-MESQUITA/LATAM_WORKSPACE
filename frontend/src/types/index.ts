// Tipos centralizados da plataforma. Espelham os schemas do backend.

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  home_workspace: string;
  is_active: boolean;
}

export interface DemoUser {
  email: string;
  full_name: string;
  role: string;
  home_workspace: string;
}

export interface MenuItem {
  key: string;
  label: string;
  path: string;
  area?: string;
}

export interface MenuSection {
  visible: boolean;
  items: MenuItem[];
}

export interface UserMenu {
  builder_studio: MenuSection;
  business_portal: MenuSection;
  admin: MenuSection;
  workspaces: string[];
  business_areas: string[];
}

export interface UserPermissions {
  view_builder_studio: boolean;
  view_business_portal: boolean;
  view_admin: boolean;
  view_datasets: boolean;
  view_data_sources: boolean;
  view_metrics: boolean;
  view_dashboards: boolean;
  upload_dataset: boolean;
  create_data_source: boolean;
  certify_dataset: boolean;
  create_etl: boolean;
  create_metric: boolean;
  create_dashboard: boolean;
  create_report: boolean;
  run_forecast: boolean;
  export_data: boolean;
  submit_for_approval: boolean;
  publish_any: boolean;
  publish_finance: boolean;
  publish_operations: boolean;
  publish_forecast: boolean;
  schedule_job: boolean;
  view_pipelines: boolean;
  create_pipeline: boolean;
  run_pipeline: boolean;
  publish_pipeline: boolean;
  view_forecasts: boolean;
  create_forecast: boolean;
  view_alerts: boolean;
  create_alert: boolean;
  manage_alerts: boolean;
  manage_users: boolean;
  manage_workspaces: boolean;
  manage_permissions: boolean;
  view_audit_logs: boolean;
  view_lineage: boolean;
  run_quality_checks: boolean;
  export_dashboard: boolean;
  view_model_registry: boolean;
  register_model: boolean;
  capabilities: string[];
}

export interface LoginResponse {
  token: string;
  user: User;
  permissions: UserPermissions;
  menu: UserMenu;
}

export interface Workspace {
  id: number;
  name: string;
  description: string;
  scope: string;
}

// ---------- Datasets ----------

export type DatasetStatus = "Draft" | "Validated" | "Certified" | "Deprecated";
export type DatasetSourceType = "Upload" | "Sample" | "Connection" | "ETL Output";
export type ColumnDtype = "string" | "integer" | "float" | "date" | "boolean";

export interface DatasetColumn {
  id: number;
  position: number;
  name: string;
  dtype: ColumnDtype | string;
  null_count: number;
  distinct_count: number;
  min_value: string | null;
  max_value: string | null;
  mean_value: number | null;
  std_value: number | null;
  sample_values: (string | number | boolean)[];
}

export interface DatasetSummary {
  id: number;
  name: string;
  description: string;
  workspace: string;
  business_area: string;
  source_type: DatasetSourceType | string;
  row_count: number;
  column_count: number;
  status: DatasetStatus | string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface Dataset extends DatasetSummary {
  source_data_source_id: number | null;
  original_filename: string;
  file_size_bytes: number;
  certified_by: string | null;
  certified_at: string | null;
  columns: DatasetColumn[];
}

export interface DatasetPreview {
  dataset_id: number;
  name: string;
  row_count: number;
  column_count: number;
  columns: string[];
  rows: Record<string, unknown>[];
  truncated: boolean;
}

export interface SampleCatalogItem {
  name: string;
  description: string;
  business_area: string;
  workspace: string;
}

// ---------- Data Sources ----------

export type DatabaseType = "PostgreSQL" | "SQL Server" | "MySQL" | "SQLite" | "DuckDB";
export type DataSourceStatus = "Active" | "Inactive" | "Pending Test" | "Error";

export interface DataSource {
  id: number;
  connection_name: string;
  database_type: DatabaseType | string;
  host: string;
  port: number;
  database_name: string;
  username: string;
  has_password: boolean;
  schema: string;
  status: DataSourceStatus | string;
  workspace: string;
  created_by: string;
  created_at: string;
  last_test_at: string | null;
  notes: string;
}

export interface DataSourceCreatePayload {
  connection_name: string;
  database_type: string;
  host?: string;
  port?: number;
  database_name?: string;
  username?: string;
  password?: string;
  schema?: string;
  workspace?: string;
  notes?: string;
}

export interface TestConnectionResult {
  success: boolean;
  message: string;
  latency_ms: number;
}

// ---------- Metrics ----------

export type MetricFormulaType =
  | "SUM"
  | "AVERAGE"
  | "COUNT"
  | "MIN"
  | "MAX"
  | "RATIO"
  | "VARIATION_ABS"
  | "VARIATION_PCT"
  | "MTD"
  | "YTD"
  | "YOY"
  | "CUSTOM_LIMITED";

export type MetricStatus = "Draft" | "Certified" | "Published" | "Deprecated";
export type OutputFormat = "number" | "currency" | "percent" | "integer";

export interface Metric {
  id: number;
  name: string;
  description: string;
  dataset_id: number;
  workspace: string;
  business_area: string;
  formula_type: MetricFormulaType | string;
  formula_config: Record<string, unknown>;
  output_format: OutputFormat | string;
  decimals: number;
  status: MetricStatus | string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface MetricCreatePayload {
  name: string;
  description?: string;
  dataset_id: number;
  workspace: string;
  business_area?: string;
  formula_type: string;
  formula_config: Record<string, unknown>;
  output_format?: string;
  decimals?: number;
}

export interface MetricPreviewPayload {
  dataset_id: number;
  formula_type: string;
  formula_config: Record<string, unknown>;
  filters?: Record<string, unknown>;
}

export interface MetricPreviewResult {
  value: number | null;
  formatted: string;
  output_format: string;
  decimals: number;
  rows_used: number;
}

// ---------- Dashboards ----------

export type WidgetType =
  | "kpi_card"
  | "bar_chart"
  | "line_chart"
  | "area_chart"
  | "pie_chart"
  | "donut_chart"
  | "table"
  | "text_box";

export type DashboardStatus =
  | "Draft"
  | "Pending Approval"
  | "Published"
  | "Archived"
  | "Deprecated";

export interface WidgetLayout {
  x: number;
  y: number;
  w: number;
  h: number;
}

// ---------------------------------------------------------------------------
// Pipelines (Phase 3b - ETL Builder)
// ---------------------------------------------------------------------------

export type StepType =
  | "source"
  | "filter"
  | "select"
  | "computed"
  | "group_by"
  | "join"
  | "union"
  | "sort"
  | "limit"
  | "target";

export type PipelineStatus = "Draft" | "Published" | "Archived";
export type RunStatus = "Running" | "Success" | "Failed";

export interface PipelineStep {
  id: number;
  pipeline_id: number;
  order_index: number;
  name: string;
  step_type: StepType | string;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface PipelineSummary {
  id: number;
  name: string;
  description: string;
  workspace: string;
  business_area: string;
  schedule_cron: string;
  status: PipelineStatus | string;
  created_by: string;
  updated_at: string;
  last_run_at: string | null;
  last_run_status: string | null;
  step_count: number;
}

export interface Pipeline extends PipelineSummary {
  created_at: string;
  published_by: string | null;
  published_at: string | null;
  archived_by: string | null;
  archived_at: string | null;
  steps: PipelineStep[];
}

export interface PipelineCreatePayload {
  name: string;
  description?: string;
  workspace?: string;
  business_area?: string;
  schedule_cron?: string;
}

export interface StepCreatePayload {
  name?: string;
  step_type: StepType | string;
  order_index?: number;
  config?: Record<string, unknown>;
}

export interface StepUpdatePayload {
  name?: string;
  step_type?: StepType | string;
  order_index?: number;
  config?: Record<string, unknown>;
}

export interface PipelinePreviewPayload {
  steps?: StepCreatePayload[];
  up_to_index?: number;
  sample_rows?: number;
}

export interface PipelinePreviewResult {
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
  dataframe_schema: { name: string; dtype: string }[];
  notes: string;
}

export interface PipelineRun {
  id: number;
  pipeline_id: number;
  triggered_by: string;
  status: RunStatus | string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  rows_in: number | null;
  rows_out: number | null;
  target_dataset_id: number | null;
  error_message: string | null;
  failed_step_index: number | null;
  failed_step_name: string | null;
  failed_step_type: string | null;
  logs: string;
}

export interface WidgetConfig {
  dataset_id?: number;
  metric_id?: number;
  metric_inline?: {
    formula_type: string;
    formula_config: Record<string, unknown>;
    output_format?: string;
    decimals?: number;
    name?: string;
  };
  dimension?: string;
  time_grain?: "day" | "week" | "month" | "quarter" | "year";
  filters?: Record<string, unknown>;
  sort?: "asc" | "desc";
  sort_by?: string;
  limit?: number;
  label?: string;
  columns?: string[];
  text_content?: string;
  style?: Record<string, unknown>;
}

export interface Widget {
  id: number;
  dashboard_id: number;
  title: string;
  widget_type: WidgetType | string;
  layout: WidgetLayout;
  config: WidgetConfig;
  created_at: string;
  updated_at: string;
}

export interface DashboardSummary {
  id: number;
  name: string;
  description: string;
  workspace: string;
  business_area: string;
  status: DashboardStatus | string;
  theme: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  widget_count: number;
}

export interface Dashboard extends DashboardSummary {
  submitted_by: string | null;
  submitted_at: string | null;
  published_by: string | null;
  published_at: string | null;
  archived_by: string | null;
  archived_at: string | null;
  widgets: Widget[];
}

export interface DashboardCreatePayload {
  name: string;
  description?: string;
  workspace: string;
  business_area?: string;
  theme?: string;
}

export interface DashboardKpiPayload {
  value: number | null;
  formatted: string;
  label: string;
  output_format: string;
  decimals: number;
  delta: number | null;
}

export interface DashboardChartSeries {
  name: string;
  values: (number | null)[];
}

export interface DashboardChartPayload {
  metric_name: string;
  output_format: string;
  decimals: number;
  categories: (string | number)[];
  series: DashboardChartSeries[];
}

export interface DashboardTablePayload {
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
}

export interface WidgetRenderResult {
  widget_type: string;
  title: string;
  kpi: DashboardKpiPayload | null;
  chart: DashboardChartPayload | null;
  table: DashboardTablePayload | null;
  text: string | null;
  rows_used: number;
  notes: string;
  widget_id?: number | null;
  layout?: WidgetLayout | null;
}

export interface WidgetPreviewPayload {
  widget_type: string;
  config: WidgetConfig;
}

// =====================
// Forecasting (Phase 4)
// =====================

export type ForecastAlgorithm = "naive_seasonal" | "linear_trend" | "holt_winters";
export type ForecastFrequency = "D" | "W" | "M" | "Q" | "Y";
export type ForecastStatusValue = "Draft" | "Published" | "Archived";
export type ForecastRunStatusValue = "Running" | "Success" | "Failed";

export interface ForecastMetrics {
  mae: number | null;
  rmse: number | null;
  mape: number | null;
  n_train?: number;
  n_test?: number;
  error?: string;
}

export interface ForecastSummary {
  id: number;
  name: string;
  description: string;
  workspace: string;
  business_area: string;
  algorithm: ForecastAlgorithm;
  horizon: number;
  frequency: ForecastFrequency;
  status: ForecastStatusValue;
  created_by: string;
  updated_at: string;
  last_run_at: string | null;
  last_run_status: ForecastRunStatusValue | null;
  last_metrics: Record<string, ForecastMetrics> | null;
  output_dataset_id: number | null;
}

export interface ForecastDetail extends ForecastSummary {
  source_dataset_id: number;
  target_column: string;
  date_column: string;
  group_by: string[];
  aggregation: "sum" | "mean";
  algorithm_params: Record<string, unknown>;
  holdout_periods: number;
  filters: Record<string, unknown>;
  created_at: string;
  published_by: string | null;
  published_at: string | null;
  archived_by: string | null;
  archived_at: string | null;
}

export interface ForecastCreatePayload {
  name: string;
  description?: string;
  workspace: string;
  business_area?: string;
  source_dataset_id: number;
  target_column: string;
  date_column: string;
  frequency?: ForecastFrequency;
  group_by?: string[];
  aggregation?: "sum" | "mean";
  algorithm?: ForecastAlgorithm;
  algorithm_params?: Record<string, unknown>;
  horizon?: number;
  holdout_periods?: number;
  filters?: Record<string, unknown>;
}

export type ForecastUpdatePayload = Partial<ForecastCreatePayload>;

export interface ForecastPoint {
  ds: string;
  y: number | null;
  yhat: number | null;
  yhat_lower: number | null;
  yhat_upper: number | null;
  is_forecast: boolean;
  group_key: string | null;
}

export interface ForecastTrainResponse {
  forecast_id: number;
  rows_in: number;
  rows_forecast: number;
  groups_count: number;
  points: ForecastPoint[];
  metrics: Record<string, ForecastMetrics>;
  notes?: string;
}

export interface ForecastRun {
  id: number;
  forecast_id: number;
  triggered_by: string;
  status: ForecastRunStatusValue;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  rows_in: number | null;
  rows_forecast: number | null;
  groups_count: number | null;
  metrics: Record<string, ForecastMetrics> | null;
  error_message: string | null;
  output_dataset_id: number | null;
}

// =====================
// Alerts & Notifications (Phase 5)
// =====================

export type AlertType =
  | "metric_threshold"
  | "metric_change"
  | "forecast_quality"
  | "pipeline_failure"
  | "dashboard_stale";

export type AlertSeverity = "info" | "warning" | "critical";

export type AlertTargetKind = "metric" | "forecast" | "pipeline" | "dashboard";

export type NotificationStatus = "unread" | "read" | "acknowledged";

export type AlertEvalStatus =
  | "ok"
  | "fired"
  | "error"
  | "cooldown"
  | "disabled"
  | "would_fire";

export interface Alert {
  id: number;
  name: string;
  description: string;
  workspace: string;
  business_area: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  target_id: number | null;
  target_kind: AlertTargetKind | null;
  rule_config: Record<string, unknown>;
  channels: string[];
  recipients: string[];
  enabled: boolean;
  cooldown_minutes: number;
  created_by: string;
  created_at: string;
  updated_at: string;
  last_evaluated_at: string | null;
  last_eval_status: string | null;
  last_fired_at: string | null;
  last_eval_error: string | null;
  fire_count: number;
}

export interface AlertCreatePayload {
  name: string;
  description?: string;
  workspace: string;
  business_area?: string;
  alert_type: AlertType;
  severity?: AlertSeverity;
  target_id?: number | null;
  target_kind?: AlertTargetKind | null;
  rule_config?: Record<string, unknown>;
  channels?: string[];
  recipients?: string[];
  enabled?: boolean;
  cooldown_minutes?: number;
}

export type AlertUpdatePayload = Partial<AlertCreatePayload>;

export interface AlertEvaluationResult {
  alert_id: number;
  fired: boolean;
  status: AlertEvalStatus;
  title: string;
  message: string;
  severity: AlertSeverity;
  context: Record<string, unknown>;
  notification_id: number | null;
  error: string | null;
}

export interface EvaluateAllResponse {
  evaluated: number;
  fired: number;
  errors: number;
  cooldowned: number;
  results: AlertEvaluationResult[];
}

export interface Notification {
  id: number;
  alert_id: number;
  alert_name: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  workspace: string;
  business_area: string;
  title: string;
  message: string;
  context: Record<string, unknown>;
  recipient_email: string;
  channels_delivered: string[];
  fired_at: string;
  status: NotificationStatus;
  read_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  ack_note: string | null;
}

export interface NotificationSummary {
  total_unread: number;
  total_unack: number;
  by_severity: Record<"info" | "warning" | "critical", number>;
  recent: Notification[];
}

// =====================
// Scheduler (Phase 6)
// =====================

export type ScheduledJobType = "pipeline_run" | "forecast_train" | "alerts_evaluate";
export type ScheduledJobRunStatus = "Running" | "Success" | "Failed" | "Skipped";

export interface ScheduledJob {
  id: number;
  name: string;
  description: string;
  workspace: string;
  business_area: string;
  job_type: ScheduledJobType;
  target_id: number | null;
  target_name: string | null;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  paused: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  last_run_status: ScheduledJobRunStatus | null;
  next_run_at: string | null;
  run_count: number;
  source_pipeline_id: number | null;
}

export interface ScheduledJobCreatePayload {
  name: string;
  description?: string;
  workspace: string;
  business_area?: string;
  job_type: ScheduledJobType;
  target_id?: number | null;
  cron_expression: string;
  timezone?: string;
  enabled?: boolean;
  paused?: boolean;
}

export type ScheduledJobUpdatePayload = Partial<ScheduledJobCreatePayload>;

export interface ScheduledJobRun {
  id: number;
  job_id: number;
  triggered_by: string;
  status: ScheduledJobRunStatus;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
}

export interface SchedulerStatus {
  running: boolean;
  active_jobs: number;
  next_runs: { apscheduler_id: string; next_run_at: string | null }[];
}

// =====================
// Ad-Hoc Reports (Phase 7)
// =====================

export interface ReportExample {
  label: string;
  sql: string;
}

export interface ReportPreviewResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
  notes: string;
  generated_sql?: string | null;
}

export interface ExtraDatasetRef {
  dataset_id: number;
  alias?: string | null;
}

export interface ReportPreviewPayload {
  dataset_id: number;
  extra_datasets?: ExtraDatasetRef[];
  sql: string;
  limit?: number;
}

export interface ReportExportPayload {
  dataset_id: number;
  extra_datasets?: ExtraDatasetRef[];
  sql: string;
  limit?: number;
}

export interface ReportSaveDatasetPayload {
  dataset_id: number;
  extra_datasets?: ExtraDatasetRef[];
  sql: string;
  output_name: string;
  description?: string;
  workspace?: string;
  business_area?: string;
}

export interface JoinSuggestion {
  left: string;
  right: string;
  label: string;
}

export interface VisualColumnRef {
  table: string;
  column: string;
  alias?: string | null;
}

export interface VisualFilter {
  table: string;
  column: string;
  operator: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "contains" | "starts_with";
  value: string;
}

export interface VisualMetric {
  table: string;
  column: string;
  aggregation: "none" | "sum" | "avg" | "count" | "min" | "max";
  alias?: string | null;
}

export interface VisualJoin {
  dataset_id: number;
  alias?: string | null;
  left_column: string;
  right_column: string;
  join_type: "inner" | "left";
}

export interface VisualReportPayload {
  primary_dataset_id: number;
  join?: VisualJoin | null;
  columns: VisualColumnRef[];
  filters: VisualFilter[];
  group_by: VisualColumnRef[];
  metrics: VisualMetric[];
  order_by?: VisualColumnRef | null;
  order_dir?: "asc" | "desc";
  limit?: number;
}

export interface SavedReport {
  id: number;
  name: string;
  description: string;
  workspace: string;
  business_area: string;
  source_dataset_id: number;
  sql_query: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  last_run_at: string | null;
  source_dataset_name?: string | null;
}

export interface SavedReportCreatePayload {
  name: string;
  description?: string;
  workspace?: string;
  business_area?: string;
  source_dataset_id: number;
  sql_query: string;
}

export type SavedReportUpdatePayload = Partial<SavedReportCreatePayload>;

export interface ReportSaveDatasetResult {
  dataset_id: number;
  name: string;
  row_count: number;
}

// =====================
// Admin (Phase 8)
// =====================

export interface AuditLogEntry {
  id: number;
  user_email: string;
  action: string;
  object_type: string;
  object_name: string;
  workspace: string;
  business_area: string;
  timestamp: string;
  details: string;
}

export interface UserCreatePayload {
  email: string;
  full_name: string;
  role: string;
  home_workspace: string;
}

export interface UserUpdatePayload {
  full_name?: string;
  role?: string;
  home_workspace?: string;
  is_active?: boolean;
}

export interface WorkspaceUpdatePayload {
  description?: string;
  scope?: string;
}

export interface PermissionsMatrix {
  roles: string[];
  capabilities: string[];
  matrix: Record<string, string[]>;
  workspace_access: Record<string, string[] | null>;
  business_areas: Record<string, string[] | null>;
}

export interface SystemStatus {
  status: string;
  app: string;
  version: string;
  environment: string;
  database_url: string;
  scheduler_running: boolean;
  scheduler_active_jobs: number;
  entity_counts: Record<string, number>;
  recent_failed_jobs: number;
}

// =====================
// Phase 9 — Extras
// =====================

export interface LineageNode {
  id: number;
  name: string;
  source_type: string;
  workspace: string;
}

export interface LineageEdge {
  from_dataset_id: number | null;
  to_dataset_id: number;
  relation_type: string;
  entity_type: string;
  entity_id: number | null;
  entity_name: string;
}

export interface DatasetLineage {
  dataset_id: number;
  dataset_name: string;
  upstream: LineageNode[];
  downstream: LineageNode[];
  edges: LineageEdge[];
}

export interface QualityCheck {
  name: string;
  column: string | null;
  passed: boolean;
  severity: string;
  message: string;
  value?: unknown;
}

export interface DatasetQuality {
  dataset_id: number;
  score: number;
  checks: QualityCheck[];
  run_at: string | null;
}

export interface RegisteredModel {
  id: number;
  name: string;
  version: string;
  model_type: string;
  algorithm: string;
  forecast_id: number | null;
  workspace: string;
  business_area: string;
  status: string;
  metrics: Record<string, unknown>;
  description: string;
  registered_by: string;
  registered_at: string;
}

export interface RegisteredModelCreatePayload {
  name: string;
  version?: string;
  model_type?: string;
  algorithm?: string;
  forecast_id?: number | null;
  workspace?: string;
  business_area?: string;
  status?: string;
  description?: string;
}
