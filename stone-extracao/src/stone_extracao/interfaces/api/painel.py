from __future__ import annotations

from decimal import Decimal
from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from stone_extracao.infrastructure.config.settings import settings
from stone_extracao.infrastructure.store.ultima_extracao import obter_ultima

router = APIRouter(tags=["painel"])


def _money(value: Decimal | float) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@router.get("/painel", response_class=HTMLResponse)
async def painel_cartao(request: Request):
    """Painel rápido sem login — última extração de cartão (em memória)."""
    ultima = obter_ultima()
    if ultima is None:
        return HTMLResponse(
            content="""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Painel Stone Extracao</title>
<style>body{font-family:system-ui,sans-serif;margin:2rem;background:#0f1419;color:#e7ecf3}
a{color:#7dd3a7}</style></head><body>
<h1>Painel — Cartão</h1>
<p>Nenhuma extração em memória ainda.</p>
<p>Rode <code>POST /cartao/conciliation?date=YYYYMMDD</code> no
<a href="/docs">/docs</a> e recarregue esta página.</p>
<p><a href="/docs">Swagger</a> · <a href="/health">Health</a></p>
</body></html>""",
            status_code=200,
        )

    s = ultima.summary()
    rows = []
    for i, t in enumerate(ultima.transactions, start=1):
        rows.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td><code>{escape(t.id_stone)}</code></td>"
            f"<td>{escape(t.cd_autorizacao or '-')}</td>"
            f"<td>{escape(t.nr_serie_maquininha)}</td>"
            f"<td>{escape(t.cd_tipo_transacao.value)}</td>"
            f"<td>{escape(str(t.cd_bandeira or '-'))}</td>"
            f"<td>{t.qt_parcelas}</td>"
            f"<td>{'S' if t.ie_transacao_parcelada else 'N'}</td>"
            f"<td>{escape(str(t.account_type or '-'))}</td>"
            f"<td class='num'>{_money(t.vl_transacao)}</td>"
            f"<td>{escape(t.dt_movimentacao.isoformat(sep=' ', timespec='seconds'))}</td>"
            f"<td>{escape(t.reference_date or '-')}</td>"
            f"<td>{escape(t.stone_code or '-')}</td>"
            f"<td><code>{escape((t.initiator_transaction_key or '-')[:48])}</code></td>"
            "</tr>"
        )

    tipo_chips = " · ".join(f"{k}: {v}" for k, v in sorted(s["por_tipo"].items()))
    term_chips = " · ".join(
        f"{k}: {v}" for k, v in sorted(s["por_terminal"].items(), key=lambda x: -x[1])[:12]
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Painel Stone Extracao — Cartão</title>
<style>
  :root {{
    --bg:#0f1419; --card:#1a222c; --text:#e7ecf3; --muted:#9aa7b5;
    --accent:#3dd68c; --line:#2a3542; --num:#f0f3f7;
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; font-family:"Segoe UI",system-ui,sans-serif;
    background:var(--bg); color:var(--text); padding:1.5rem;
  }}
  h1 {{ margin:0 0 .25rem; font-size:1.5rem; }}
  .sub {{ color:var(--muted); margin-bottom:1.25rem; font-size:.95rem; }}
  .cards {{
    display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
    gap:.75rem; margin-bottom:1rem;
  }}
  .card {{
    background:var(--card); border:1px solid var(--line); border-radius:10px;
    padding:.9rem 1rem;
  }}
  .card .label {{ color:var(--muted); font-size:.75rem; text-transform:uppercase; letter-spacing:.04em; }}
  .card .value {{ font-size:1.25rem; font-weight:650; margin-top:.25rem; }}
  .meta {{ color:var(--muted); font-size:.85rem; margin: .5rem 0 1rem; line-height:1.5; }}
  .note {{
    background:#1e2a22; border:1px solid #2f4a3a; color:#b7e0c7;
    padding:.75rem 1rem; border-radius:8px; margin-bottom:1rem; font-size:.9rem;
  }}
  .toolbar {{ display:flex; gap:.75rem; flex-wrap:wrap; margin-bottom:1rem; align-items:center; }}
  a.btn {{
    display:inline-block; background:var(--accent); color:#062816; font-weight:600;
    text-decoration:none; padding:.45rem .9rem; border-radius:8px; font-size:.9rem;
  }}
  a.link {{ color:var(--accent); }}
  input[type=search] {{
    flex:1; min-width:200px; background:var(--card); border:1px solid var(--line);
    color:var(--text); padding:.5rem .75rem; border-radius:8px;
  }}
  .wrap {{ overflow:auto; border:1px solid var(--line); border-radius:10px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.82rem; min-width:1100px; }}
  th, td {{ padding:.45rem .55rem; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
  th {{ position:sticky; top:0; background:#152029; color:var(--muted); font-weight:600; }}
  tr:hover td {{ background:#152029; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; color:var(--num); }}
  code {{ font-size:.78rem; }}
</style>
</head>
<body>
  <h1>Vendas extraídas — Cartão</h1>
  <p class="sub">
    Última extração em memória · sem login ·
    <a class="link" href="/docs">Swagger</a> ·
    <a class="link" href="/painel/api/cartao">JSON</a>
  </p>

  <div class="note">
    O portal Stone “Vendas feitas” pode mostrar menos registros que o arquivo de conciliação
    (capturas, pré-pago, horários UTC/local, etc.). Use esta tabela para cruzar
    <strong>id_stone / NSU</strong> e valores com o portal.
  </div>

  <div class="cards">
    <div class="card"><div class="label">Data ref.</div><div class="value">{escape(s['reference_date'])}</div></div>
    <div class="card"><div class="label">Total de vendas</div><div class="value">{s['total_vendas']}</div></div>
    <div class="card"><div class="label">Total vendido</div><div class="value">{_money(s['total_vendido'])}</div></div>
    <div class="card"><div class="label">Ticket médio</div><div class="value">{_money(s['ticket_medio'])}</div></div>
    <div class="card"><div class="label">Publicadas na fila</div><div class="value">{s['published_count']}</div></div>
    <div class="card"><div class="label">Fonte</div><div class="value" style="font-size:1rem">{escape(s['source'])}</div></div>
  </div>

  <p class="meta">
    Extraído em: {escape(s['extracted_at'])}<br>
    Por tipo: {escape(tipo_chips)}<br>
    Por terminal (top): {escape(term_chips)}<br>
    Fila: <code>{escape(settings.RABBITMQ_QUEUE_CARTAO)}</code>
  </p>

  <div class="toolbar">
    <input id="q" type="search" placeholder="Filtrar por id_stone, terminal, auth, tipo...">
    <a class="btn" href="/painel">Recarregar</a>
  </div>

  <div class="wrap">
    <table id="tx">
      <thead>
        <tr>
          <th>#</th>
          <th>id_stone (NSU)</th>
          <th>autorização</th>
          <th>terminal</th>
          <th>tipo</th>
          <th>bandeira</th>
          <th>parc.</th>
          <th>parc?</th>
          <th>account</th>
          <th>valor</th>
          <th>dt_movimentacao</th>
          <th>ref_date</th>
          <th>stone_code</th>
          <th>initiator</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>

<script>
const q = document.getElementById('q');
const rows = [...document.querySelectorAll('#tx tbody tr')];
q.addEventListener('input', () => {{
  const v = q.value.trim().toLowerCase();
  rows.forEach(r => {{
    r.style.display = !v || r.innerText.toLowerCase().includes(v) ? '' : 'none';
  }});
}});
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/painel/api/cartao")
async def painel_api_cartao():
    ultima = obter_ultima()
    if ultima is None:
        return JSONResponse(
            {"detail": "Nenhuma extração em memória. Rode POST /cartao/conciliation primeiro."},
            status_code=404,
        )
    return {
        "summary": ultima.summary(),
        "queue": settings.RABBITMQ_QUEUE_CARTAO,
        "transactions": [t.model_dump(mode="json") for t in ultima.transactions],
    }
