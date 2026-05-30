import { PageContainer } from "@/components/layout/PageContainer";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

/**
 * Página placeholder reutilizável para módulos que ainda não foram
 * implementados na fase atual. Quando avançarmos para as fases seguintes
 * (upload, ETL, dashboard, forecasting, etc.) substituímos cada um por
 * sua implementação real.
 */
export default function Placeholder({
  title,
  subtitle,
  description,
  phase,
}: {
  title: string;
  subtitle?: string;
  description?: string;
  phase?: string;
}) {
  return (
    <PageContainer title={title} subtitle={subtitle}>
      <Card>
        <EmptyState
          title={`${title} - em construção`}
          description={
            description ??
            "Este módulo será habilitado nas próximas fases da implementação."
          }
          icon={
            <div className="h-12 w-12 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center text-2xl">
              ◌
            </div>
          }
          action={
            phase ? (
              <span className="badge bg-brand-50 text-brand-700">{phase}</span>
            ) : undefined
          }
        />
      </Card>
    </PageContainer>
  );
}
