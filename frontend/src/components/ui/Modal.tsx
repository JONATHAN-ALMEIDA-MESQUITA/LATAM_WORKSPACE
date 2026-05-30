import { useEffect, type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}

const sizeClasses = {
  sm: "max-w-md",
  md: "max-w-xl",
  lg: "max-w-3xl",
};

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  size = "md",
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-900/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className={`w-full ${sizeClasses[size]} bg-white rounded-2xl shadow-card flex flex-col max-h-[90vh]`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-ink-100">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-base font-semibold text-ink-900">{title}</h3>
              {subtitle && <p className="mt-0.5 text-sm text-ink-500">{subtitle}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              className="text-ink-400 hover:text-ink-700 text-xl leading-none"
              aria-label="Fechar"
            >
              ×
            </button>
          </div>
        </div>
        <div className="px-5 py-4 overflow-y-auto flex-1">{children}</div>
        {footer && (
          <div className="px-5 py-3 border-t border-ink-100 bg-ink-50/50 rounded-b-2xl">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
