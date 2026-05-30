import type { ReactNode } from "react";

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6">
      {icon && <div className="mb-4 text-ink-400">{icon}</div>}
      <h3 className="text-base font-semibold text-ink-900">{title}</h3>
      {description && (
        <p className="mt-1 max-w-md text-sm text-ink-500">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
