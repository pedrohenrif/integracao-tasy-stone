import { useEffect, useState } from "react";
import { filasApi } from "../api/client";
import type { FilaInfo } from "../types";

export function FilasPage() {
  const [items, setItems] = useState<FilaInfo[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await filasApi();
      setItems(data.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 15000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div>
      <header className="page-head">
        <h1>Filas RabbitMQ</h1>
        <p className="muted">Atualiza a cada 15s · Management API</p>
        <button type="button" className="btn" onClick={() => void load()} disabled={loading}>
          Atualizar
        </button>
      </header>
      {error && <p className="error">{error}</p>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Fila</th>
              <th>Ready</th>
              <th>Unacked</th>
              <th>Total</th>
              <th>Consumers</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {items.map((f) => (
              <tr key={f.name}>
                <td>
                  <code>{f.name}</code>
                  {f.error ? <div className="error small">{f.error}</div> : null}
                </td>
                <td>{f.messages_ready ?? "-"}</td>
                <td>{f.messages_unacknowledged ?? "-"}</td>
                <td>{f.messages ?? "-"}</td>
                <td>{f.consumers ?? "-"}</td>
                <td>{f.state || (f.exists === false ? "n/a" : "-")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
