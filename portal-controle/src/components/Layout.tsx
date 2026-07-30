import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/integracoes", label: "Integrações" },
  { to: "/erros", label: "Erros / Sem Tesouraria" },
  { to: "/auditoria", label: "Auditoria", admin: true },
  { to: "/scheduler", label: "Scheduler", admin: true },
  { to: "/cadastros/maquininhas", label: "Maquininhas" },
  { to: "/cadastros/mapeamentos", label: "Mapeamentos" },
  { to: "/filas", label: "Filas" },
  { to: "/acessos", label: "Logs de acesso", admin: true },
];

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src="/cotolengo.png" alt="Complexo de Saúde Pequeno Cotolengo" />
          <strong>Portal Stone → Tasy</strong>
          <span>Controle de integrações</span>
        </div>
        <nav>
          {links
            .filter((l) => !l.admin || user?.admin)
            .map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => (isActive ? "active" : "")}>
                {l.label}
              </NavLink>
            ))}
        </nav>
        <div className="sidebar-foot">
          <div className="user-box">
            <strong>{user?.nome}</strong>
            <span>
              {user?.login}
              {user?.admin ? " · admin" : ""}
            </span>
          </div>
          <button type="button" className="btn ghost" onClick={logout}>
            Sair
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
