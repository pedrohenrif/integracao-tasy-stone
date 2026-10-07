import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

type NavItem = { to: string; label: string; end?: boolean; admin?: boolean };

const groups: Array<{ title: string; items: NavItem[] }> = [
  {
    title: "Operação",
    items: [
      { to: "/", label: "Dashboard", end: true },
      { to: "/integracoes", label: "Integrações" },
      { to: "/movimentos", label: "Movimentos Stone" },
      { to: "/erros", label: "Reprocessar" },
      { to: "/filas", label: "Filas" },
    ],
  },
  {
    title: "Cadastros",
    items: [
      { to: "/cadastros/maquininhas", label: "Maquininhas" },
      { to: "/cadastros/mapeamentos", label: "Mapeamentos" },
    ],
  },
  {
    title: "Ajuda",
    items: [{ to: "/ajuda", label: "Como usar" }],
  },
  {
    title: "Admin",
    items: [
      { to: "/auditoria", label: "Auditoria", admin: true },
      { to: "/scheduler", label: "Scheduler", admin: true },
      { to: "/purge", label: "Purge Stone", admin: true },
      { to: "/usuarios", label: "Usuários", admin: true },
      { to: "/acessos", label: "Logs de acesso", admin: true },
    ],
  },
];

export function Layout() {
  const { user, logout } = useAuth();
  const [navOpen, setNavOpen] = useState(false);

  return (
    <div className="shell">
      <aside className={`sidebar${navOpen ? " nav-open" : ""}`}>
        <div className="brand">
          <div className="brand-top">
            <img className="brand-logo" src="/cotolengo.png" alt="Complexo de Saúde Pequeno Cotolengo" />
            <button
              type="button"
              className="nav-toggle"
              aria-expanded={navOpen}
              onClick={() => setNavOpen((v) => !v)}
            >
              {navOpen ? "Fechar" : "Menu"}
            </button>
          </div>
          <strong>Portal Stone → Tasy</strong>
          <span>Controle de integrações</span>
        </div>
        <nav>
          {groups.map((g) => {
            const items = g.items.filter((l) => !l.admin || user?.admin);
            if (!items.length) return null;
            return (
              <div key={g.title} className="nav-group">
                <p className="nav-group-title">{g.title}</p>
                {items.map((l) => (
                  <NavLink
                    key={l.to}
                    to={l.to}
                    end={l.end}
                    className={({ isActive }) => (isActive ? "active" : "")}
                    onClick={() => setNavOpen(false)}
                  >
                    {l.label}
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="sidebar-foot">
          <div className="user-box">
            <strong>{user?.nome}</strong>
            <span>
              {user?.login}
              {user?.admin ? " · admin" : " · financeiro"}
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
