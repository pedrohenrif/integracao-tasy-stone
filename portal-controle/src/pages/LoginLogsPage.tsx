import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { loginLogsApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";

type LogRow = {
  nr_sequencia: number;
  ds_login: string;
  ds_nome?: string;
  ie_sucesso: string;
  ds_ip?: string;
  ds_mensagem?: string;
  dt_evento: string;
};

export function LoginLogsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<LogRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user?.admin) return;
    loginLogsApi(150)
      .then((r) => setItems((r.items || []) as LogRow[]))
      .catch((e) => setError(e.message));
  }, [user?.admin]);

  if (!user?.admin) return <Navigate to="/" replace />;

  return (
    <div>
      <header className="page-head">
        <h1>Logs de acesso</h1>
        <p className="muted">Somente admin · portal_login_log</p>
      </header>
      {error && <p className="error">{error}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Quando</th>
              <th>Login</th>
              <th>Nome</th>
              <th>OK?</th>
              <th>IP</th>
              <th>Mensagem</th>
            </tr>
          </thead>
          <tbody>
            {items.map((l) => (
              <tr key={l.nr_sequencia}>
                <td>{l.dt_evento}</td>
                <td>{l.ds_login}</td>
                <td>{l.ds_nome || "-"}</td>
                <td>
                  <span className={`badge ${l.ie_sucesso === "S" ? "s5" : "s7"}`}>
                    {l.ie_sucesso === "S" ? "Sim" : "Não"}
                  </span>
                </td>
                <td>{l.ds_ip || "-"}</td>
                <td>{l.ds_mensagem || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
