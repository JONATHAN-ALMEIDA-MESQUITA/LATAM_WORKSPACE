import type { ReactNode } from "react";

type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-ink-100 text-ink-700",
  brand: "bg-brand-50 text-brand-700",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-700",
  danger: "bg-rose-50 text-rose-700",
  info: "bg-sky-50 text-sky-700",
};

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return <span className={`badge ${toneClasses[tone]} ${className}`}>{children}</span>;
}
