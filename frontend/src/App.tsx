import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import BusinessAreaView from "@/pages/business/BusinessAreaView";
import AdHocReportBuilder from "@/pages/builder/AdHocReportBuilder";
import AlertList from "@/pages/builder/AlertList";
import AuditLogViewer from "@/pages/admin/AuditLogViewer";
import PermissionsMatrix from "@/pages/admin/PermissionsMatrix";
import SystemJobsDashboard from "@/pages/admin/SystemJobsDashboard";
import UsersList from "@/pages/admin/UsersList";
import WorkspacesList from "@/pages/admin/WorkspacesList";
import DashboardBuilder from "@/pages/builder/DashboardBuilder";
import DataSources from "@/pages/builder/DataSources";
import DatasetExplorer from "@/pages/builder/DatasetExplorer";
import ForecastEditor from "@/pages/builder/ForecastEditor";
import ForecastList from "@/pages/builder/ForecastList";
import MetricBuilder from "@/pages/builder/MetricBuilder";
import ModelRegistryList from "@/pages/builder/ModelRegistryList";
import PipelineEditor from "@/pages/builder/PipelineEditor";
import PipelineList from "@/pages/builder/PipelineList";
import PublishCenter from "@/pages/builder/PublishCenter";
import SchedulerList from "@/pages/builder/SchedulerList";
import UploadData from "@/pages/builder/UploadData";
import HomePage from "@/pages/Home";
import LoginPage from "@/pages/Login";
import NotificationCenter from "@/pages/NotificationCenter";
import { useAuthStore } from "@/store/authStore";

export default function App() {
  const token = useAuthStore((s) => s.token);
  const refresh = useAuthStore((s) => s.refresh);

  // Revalida o token em qualquer reload (mantém menu/permissions atualizados).
  useEffect(() => {
    if (token) refresh();
  }, [token, refresh]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />

        {/* Builder Studio - Fase 2: Data Sources, Upload Data, Dataset Explorer */}
        <Route path="builder/data-sources" element={<DataSources />} />
        <Route path="builder/upload-data" element={<UploadData />} />
        <Route path="builder/dataset-explorer" element={<DatasetExplorer />} />
        <Route path="builder/pipelines" element={<PipelineList />} />
        <Route path="builder/pipelines/:id" element={<PipelineEditor />} />
        <Route path="builder/metric-builder" element={<MetricBuilder />} />
        <Route path="builder/dashboard-builder" element={<DashboardBuilder />} />
        <Route path="builder/ad-hoc-report" element={<AdHocReportBuilder />} />
        <Route path="builder/forecasts" element={<ForecastList />} />
        <Route path="builder/forecasts/:id" element={<ForecastEditor />} />
        <Route path="builder/model-registry" element={<ModelRegistryList />} />
        <Route path="builder/forecasting" element={<Navigate to="/builder/forecasts" replace />} />
        <Route path="builder/alerts" element={<AlertList />} />
        <Route path="notifications" element={<NotificationCenter />} />
        <Route path="builder/scheduler" element={<SchedulerList />} />
        <Route path="builder/publish-center" element={<PublishCenter />} />

        {/* Business Portal */}
        <Route
          path="business/operations"
          element={
            <BusinessAreaView
              businessArea="Operations"
              title="Operations"
              subtitle="Indicadores operacionais publicados"
            />
          }
        />
        <Route
          path="business/finance"
          element={
            <BusinessAreaView
              businessArea="Finance"
              title="Finance"
              subtitle="Indicadores financeiros publicados"
            />
          }
        />
        <Route
          path="business/supplier"
          element={
            <BusinessAreaView
              businessArea="Supplier"
              title="Supplier"
              subtitle="Performance de fornecedores"
            />
          }
        />
        <Route
          path="business/sales"
          element={
            <BusinessAreaView
              businessArea="Sales"
              title="Sales"
              subtitle="Indicadores comerciais publicados"
            />
          }
        />
        <Route
          path="business/latam-executive"
          element={
            <BusinessAreaView
              businessArea="Executive"
              title="LATAM Executive"
              subtitle="Visão executiva regional consolidada"
              allowAllAreas
            />
          }
        />

        {/* Admin — Fase 8 */}
        <Route path="admin/users" element={<UsersList />} />
        <Route path="admin/workspaces" element={<WorkspacesList />} />
        <Route path="admin/permissions" element={<PermissionsMatrix />} />
        <Route path="admin/audit-logs" element={<AuditLogViewer />} />
        <Route path="admin/system-jobs" element={<SystemJobsDashboard />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
