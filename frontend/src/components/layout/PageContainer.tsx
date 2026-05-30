import type { ReactNode } from "react";

export function PageContainer({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="px-6 py-6">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-ink-900 tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-ink-500">{subtitle}</p>}
        </div>
        {actions}
      </div>
      {children}
    </div>
  );
}
