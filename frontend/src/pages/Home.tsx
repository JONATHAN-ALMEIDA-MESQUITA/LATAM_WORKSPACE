import { Link } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { PageContainer } from "@/components/layout/PageContainer";
import { useAuthStore } from "@/store/authStore";

export default function HomePage() {
  const user = useAuthStore((s) => s.user);
  const menu = useAuthStore((s) => s.menu);
  const permissions = useAuthStore((s) => s.permissions);

  return (
    <PageContainer
      title={`Bem-vindo${user ? `, ${user.full_name.split(" ")[0]}` : ""}`}
      subtitle="Visão geral da plataforma e acessos do seu perfil."
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card title="Seu perfil" subtitle="Identidade e contexto de acesso">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-ink-500">Nome</dt>
              <dd className="font-medium text-ink-900">{user?.full_name ?? "-"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ink-500">E-mail</dt>
              <dd className="font-medium text-ink-900">{user?.email ?? "-"}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ink-500">Role</dt>
              <dd>
                <Badge tone="brand">{user?.role ?? "-"}</Badge>
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ink-500">Workspace home</dt>
              <dd className="font-medium text-ink-900">{user?.home_workspace ?? "-"}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Workspaces disponíveis" subtitle="Definidos pelo seu RBAC">
          <div className="flex flex-wrap gap-2">
            {menu?.workspaces?.length ? (
              menu.workspaces.map((w) => (
                <Badge key={w} tone={w === "LATAM" ? "brand" : "neutral"}>
                  {w}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-ink-500">Nenhum workspace.</span>
            )}
          </div>
          <div className="mt-4 text-xs text-ink-500">
            O backend valida cada operação por workspace - não basta ver no menu.
          </div>
        </Card>

        <Card title="Áreas de negócio" subtitle="Acessíveis no Business Portal">
          <div className="flex flex-wrap gap-2">
            {menu?.business_areas?.length ? (
              menu.business_areas.map((a) => (
                <Badge key={a} tone="info">
                  {a}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-ink-500">Nenhuma área.</span>
            )}
          </div>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title="Builder Studio" subtitle="Criar datasets, ETL, métricas e dashboards">
          {menu?.builder_studio?.visible ? (
            <div className="grid grid-cols-2 gap-2">
              {menu.builder_studio.items.map((item) => (
                <Link
                  key={item.key}
                  to={item.path}
                  className="block rounded-lg border border-ink-200 px-3 py-2 text-sm hover:border-brand-400 hover:bg-brand-50 transition-colors"
                >
                  {item.label}
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-sm text-ink-500">
              Seu perfil não tem acesso ao Builder Studio.
            </div>
          )}
        </Card>

        <Card title="Business Portal" subtitle="Consumir dashboards publicados">
          {menu?.business_portal?.visible ? (
            <div className="grid grid-cols-2 gap-2">
              {menu.business_portal.items.map((item) => (
                <Link
                  key={item.key}
                  to={item.path}
                  className="block rounded-lg border border-ink-200 px-3 py-2 text-sm hover:border-brand-400 hover:bg-brand-50 transition-colors"
                >
                  {item.label}
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-sm text-ink-500">
              Seu perfil não tem acesso ao Business Portal.
            </div>
          )}
        </Card>
      </div>

      <div className="mt-6">
        <Card title="Capabilities do perfil (debug)" subtitle="Conjunto retornado pelo backend">
          <div className="flex flex-wrap gap-1.5">
            {permissions?.capabilities?.length ? (
              permissions.capabilities.map((c) => (
                <code
                  key={c}
                  className="text-[11px] bg-ink-100 text-ink-700 px-2 py-0.5 rounded"
                >
                  {c}
                </code>
              ))
            ) : (
              <span className="text-sm text-ink-500">Sem capabilities.</span>
            )}
          </div>
        </Card>
      </div>
    </PageContainer>
  );
}
