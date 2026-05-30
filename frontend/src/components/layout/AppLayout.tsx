import { Outlet, Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function AppLayout() {
  const token = useAuthStore((s) => s.token);
  if (!token) return <Navigate to="/login" replace />;

  return (
    <div className="flex min-h-screen bg-ink-50">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <Header />
        <main className="flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
