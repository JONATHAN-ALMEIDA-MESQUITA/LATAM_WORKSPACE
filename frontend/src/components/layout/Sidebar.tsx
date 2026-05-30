import { NavLink } from "react-router-dom";
import type { MenuSection } from "@/types";
import { useAuthStore } from "@/store/authStore";

function SidebarSection({
  title,
  section,
}: {
  title: string;
  section?: MenuSection;
}) {
  if (!section || !section.visible || section.items.length === 0) return null;
  return (
    <div className="mt-6">
      <div className="px-3 mb-2 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
        {title}
      </div>
      <div className="space-y-0.5">
        {section.items.map((item) => (
          <NavLink
            key={item.key}
            to={item.path}
            className={({ isActive }) =>
              [
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700 font-medium"
                  : "text-ink-700 hover:bg-ink-100",
              ].join(" ")
            }
          >
            <span className="h-1.5 w-1.5 rounded-full bg-current opacity-50" />
            {item.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

export function Sidebar() {
  const menu = useAuthStore((s) => s.menu);
  const user = useAuthStore((s) => s.user);

  return (
    <aside className="hidden lg:flex flex-col w-64 shrink-0 border-r border-ink-200 bg-white h-screen sticky top-0">
      <div className="px-5 py-5 border-b border-ink-100 flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white flex items-center justify-center font-bold">
          L
        </div>
        <div>
          <div className="text-sm font-semibold text-ink-900 leading-tight">
            LATAM Analytics
          </div>
          <div className="text-[11px] text-ink-500">Platform Demo</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-6">
        <div className="mt-4">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              [
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700 font-medium"
                  : "text-ink-700 hover:bg-ink-100",
              ].join(" ")
            }
          >
            <span className="h-1.5 w-1.5 rounded-full bg-current opacity-50" />
            Home
          </NavLink>
        </div>
        <SidebarSection title="Builder Studio" section={menu?.builder_studio} />
        <SidebarSection title="Business Portal" section={menu?.business_portal} />
        <SidebarSection title="Admin" section={menu?.admin} />
      </nav>

      <div className="px-4 py-3 border-t border-ink-100 text-xs text-ink-500">
        {user ? (
          <div className="truncate">
            Logado como <span className="font-medium text-ink-700">{user.full_name}</span>
          </div>
        ) : (
          "Não autenticado"
        )}
      </div>
    </aside>
  );
}
