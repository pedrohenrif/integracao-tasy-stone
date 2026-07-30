from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # RabbitMQ
    RABBITMQ_URL: str = "amqp://stone:stone@localhost:5673/"
    RABBITMQ_QUEUE_CARTAO: str = "stone.cartao.transactions"
    RABBITMQ_QUEUE_PIX: str = "stone.pix.transactions"
    RABBITMQ_EXCHANGE: str = "stone.direct"

    # Stone API — Cartão (StoneCode)
    STONE_MERCHANT_ID: str = "116852622"
    STONE_CONCILIATION_BASE_URL: str = "https://conciliation.stone.com.br/v2"
    STONE_API_TOKEN: str = ""

    # Stone API — PIX (CNPJ merchant do e-mail)
    STONE_PIX_MERCHANT_ID: str = "76610690000162"

    # Fallback local (só se STONE_USE_SAMPLE=true)
    STONE_USE_SAMPLE: bool = False
    STONE_CARTAO_SAMPLE_PATH: str = "../stone_movimento_20260708_cartao.xml"
    STONE_PIX_SAMPLE_PATH: str = "../stone_movimento_20260708_pix.xml"

    # Webhook PIX (opcional: header de validação quando Stone fornecer)
    PIX_WEBHOOK_SECRET: str = ""

    # Rotina diária cartão D-1 (sempre o dia anterior, fuso Brasil)
    # Em prod/homolog: true + uvicorn SEM --reload (evita job duplicado)
    # Horário via .env: CARTAO_CRON_HOUR (0-23) + CARTAO_CRON_MINUTE (0-59)
    CARTAO_CRON_ENABLED: bool = False
    CARTAO_CRON_HOUR: int = 1
    CARTAO_CRON_MINUTE: int = 0
    CARTAO_CRON_TZ: str = "America/Sao_Paulo"

    APP_NAME: str = "stone-extracao"
    APP_ENV: str = "homolog"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )


settings = Settings()
