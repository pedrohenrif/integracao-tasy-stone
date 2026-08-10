"""API do portal de controle (Postgres + auth + filas).

Uso:
  poetry run python -m tasy_insercao.painel
  # React: cd portal-controle && npm run dev  → http://localhost:5173
"""

from __future__ import annotations

import uvicorn

from tasy_insercao.infrastructure.config.settings import settings


def main() -> None:
    # reload só em desenvolvimento local — na VM (homolog/prod) o WatchFiles
    # reinicia o processo no meio das requests e gera Failed to fetch no portal.
    env = (settings.APP_ENV or "").strip().lower()
    use_reload = env in {"local", "dev", "development"}
    uvicorn.run(
        "tasy_insercao.interfaces.api.painel:app",
        host="0.0.0.0",
        port=8001,
        reload=use_reload,
    )


if __name__ == "__main__":
    main()
