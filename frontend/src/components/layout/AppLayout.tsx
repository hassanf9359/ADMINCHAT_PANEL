import { useEffect } from 'react';
import { Navigate, Outlet, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuthStore } from '../../stores/authStore';
import '../../stores/themeStore'; // ensure theme is applied on import
import { LogOut, User } from 'lucide-react';

function roleBadgeColor(role: string): string {
  switch (role) {
    case 'super_admin':
      return 'bg-purple/15 text-purple border-purple/20';
    case 'admin':
      return 'bg-accent/15 text-accent border-accent/20';
    default:
      return 'bg-green/15 text-green border-green/20';
  }
}

function formatRole(role: string): string {
  return role.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AppLayout() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const fetchCurrentUser = useAuthStore((s) => s.fetchCurrentUser);
  const navigate = useNavigate();

  // Verify token is still valid on mount
  useEffect(() => {
    if (isAuthenticated) {
      fetchCurrentUser();
    }
  }, [isAuthenticated, fetchCurrentUser]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="flex h-screen overflow-hidden bg-bg-page relative">
      {/* Flowing gradient background (visible in light theme) */}
      <div className="flowing-bg" aria-hidden="true" />
      <Sidebar />
      {/* Spacer for fixed sidebar - always 64px (w-16) */}
      <div className="w-16 shrink-0" />
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
        {/* Top header bar */}
        <header className="flex items-center justify-end h-12 px-8 border-b border-border-subtle bg-bg-page glass-header shrink-0">
          <div className="flex items-center gap-3">
            {user && (
              <>
                <span
                  className={`inline-flex items-center px-2.5 py-1 text-[10px] font-medium rounded border ${roleBadgeColor(user.role)}`}
                >
                  {formatRole(user.role)}
                </span>
                <div className="flex items-center gap-2">
                  <div className="flex items-center justify-center w-7 h-7 rounded-full bg-bg-elevated border border-border">
                    <User size={14} className="text-text-secondary" />
                  </div>
                  <span className="text-sm text-text-primary font-medium">
                    {user.display_name || user.username}
                  </span>
                </div>
              </>
            )}
            <button
              onClick={handleLogout}
              className="flex items-center justify-center w-7 h-7 rounded-lg text-text-muted hover:text-red hover:bg-red/10 transition-colors"
              title="Logout"
            >
              <LogOut size={14} />
            </button>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>

        {/* Footer */}
        <footer className="flex flex-col items-center justify-center py-2 px-8 border-t border-border-subtle bg-bg-sidebar shrink-0">
          <span className="text-[10px] text-text-placeholder font-mono leading-tight">
            Powered By ADMINCHAT PANEL v{__APP_VERSION__} ({__BUILD_VERSION__})
          </span>
          <span className="text-[9px] text-text-placeholder leading-tight">
            &reg;2026 NovaHelix &amp; SAKAKIBARA
          </span>
        </footer>
      </div>
    </div>
  );
}
