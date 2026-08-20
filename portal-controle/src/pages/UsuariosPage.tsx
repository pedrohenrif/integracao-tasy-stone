import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import {
  atualizarUsuarioApi,
  criarUsuarioApi,
  desativarUsuarioApi,
  usuariosApi,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { PortalUsuario } from "../types";

export function UsuariosPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<PortalUsuario[]>([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [login, setLogin] = useState("");
  const [nome, setNome] = useState("");
  const [password, setPassword] = useState("");
  const [admin, setAdmin] = useState(false);

  const load = useCallback(() => {
    usuariosApi()
      .then((r) => setItems(r.items || []))
      .catch((e) => setError(e instanceof Error ? e.message : "Falha ao listar"));
  }, []);

  useEffect(() => {
    if (!user?.admin) return;
    load();
  }, [user?.admin, load]);

  if (!user?.admin) return <Navigate to="/" replace />;

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMsg("");
    try {
      await criarUsuarioApi({ login, nome, password, admin });
      setLogin("");
      setNome("");
      setPassword("");
      setAdmin(false);
      setMsg("Usuário criado.");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar");
    } finally {
      setBusy(false);
    }
  }

  async function onToggleAtivo(u: PortalUsuario) {
    if (u.id === user?.id && u.ativo) {
      setError("Não é permitido desativar o próprio usuário");
      return;
    }
    setBusy(true);
    setError("");
    setMsg("");
    try {
      if (u.ativo) {
        await desativarUsuarioApi(u.id);
        setMsg(`Usuário ${u.login} desativado.`);
      } else {
        await atualizarUsuarioApi(u.id, { ativo: true });
        setMsg(`Usuário ${u.login} reativado.`);
      }
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar");
    } finally {
      setBusy(false);
    }
  }

  async function onToggleAdmin(u: PortalUsuario) {
    if (u.id === user?.id && u.admin) {
      setError("Não é permitido remover o próprio perfil admin");
      return;
    }
    setBusy(true);
    setError("");
    setMsg("");
    try {
      await atualizarUsuarioApi(u.id, { admin: !u.admin });
      setMsg(`Perfil de ${u.login} atualizado.`);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar perfil");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <header className="page-head">
        <h1>Usuários</h1>
        <p className="muted">Somente admin · criar e desativar acessos do portal</p>
      </header>
      {error && <p className="error">{error}</p>}
      {msg && <p className="ok-msg">{msg}</p>}

      <form className="form-grid" onSubmit={(e) => void onCreate(e)}>
        <label>
          Login
          <input
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            required
            autoComplete="off"
          />
        </label>
        <label>
          Nome
          <input value={nome} onChange={(e) => setNome(e.target.value)} required />
        </label>
        <label>
          Senha
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={4}
            autoComplete="new-password"
          />
        </label>
        <label>
          Perfil
          <select
            value={admin ? "admin" : "financeiro"}
            onChange={(e) => setAdmin(e.target.value === "admin")}
          >
            <option value="financeiro">Financeiro</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        <div style={{ alignSelf: "end" }}>
          <button type="submit" className="btn" disabled={busy}>
            Criar usuário
          </button>
        </div>
      </form>

      <div className="table-wrap" style={{ marginTop: "1.25rem" }}>
        <table>
          <thead>
            <tr>
              <th>Login</th>
              <th>Nome</th>
              <th>Perfil</th>
              <th>Ativo</th>
              <th>Último login</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id}>
                <td>{u.login}</td>
                <td>{u.nome}</td>
                <td>
                  <span className={`badge ${u.admin ? "s5" : "s1"}`}>
                    {u.admin ? "Admin" : "Financeiro"}
                  </span>
                </td>
                <td>
                  <span className={`badge ${u.ativo ? "s5" : "s7"}`}>
                    {u.ativo ? "Sim" : "Não"}
                  </span>
                </td>
                <td>{u.dt_ultimo_login || "-"}</td>
                <td style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="btn btn-sm ghost"
                    disabled={busy || u.id === user?.id}
                    onClick={() => void onToggleAdmin(u)}
                  >
                    {u.admin ? "Tornar financeiro" : "Tornar admin"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm ghost"
                    disabled={busy || (u.id === user?.id && u.ativo)}
                    onClick={() => void onToggleAtivo(u)}
                  >
                    {u.ativo ? "Desativar" : "Reativar"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
