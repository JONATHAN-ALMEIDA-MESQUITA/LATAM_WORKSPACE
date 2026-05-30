import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
  bodyClassName = "",
}: CardProps) {
  return (
    <div className={`card ${className}`}>
      {(title || actions) && (
        <div className="flex items-start justify-between gap-4 p-5 border-b border-ink-100">
          <div>
            {title && <h3 className="text-base font-semibold text-ink-900">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-sm text-ink-500">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </div>
  );
}
