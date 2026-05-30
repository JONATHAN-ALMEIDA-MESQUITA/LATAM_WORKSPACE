import { useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useAuthStore } from "@/store/authStore";
import { NotificationBell } from "./NotificationBell";

export function Header() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="sticky top-0 z-20 bg-white/85 backdrop-blur border-b border-ink-200">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <Badge tone="brand">Demo</Badge>
          <span className="text-sm text-ink-500 hidden md:inline">
            Workspace: <span className="text-ink-800 font-medium">{user?.home_workspace ?? "-"}</span>
          </span>
        </div>
        <div className="flex items-center gap-3">
          <NotificationBell />
          {user && (
            <div className="text-right hidden sm:block">
              <div className="text-sm font-medium text-ink-900 leading-tight">
                {user.full_name}
              </div>
              <div className="text-[11px] text-ink-500">{user.role}</div>
            </div>
          )}
          <div className="h-9 w-9 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-semibold">
            {user?.full_name?.charAt(0) ?? "?"}
          </div>
          <Button variant="ghost" onClick={handleLogout} className="text-sm">
            Sair
          </Button>
        </div>
      </div>
    </header>
  );
}
