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

    # Backup físico do XML de cartão (VM) — útil para auditoria / dia sem captura
    STONE_XML_BACKUP_ENABLED: bool = True
    STONE_XML_BACKUP_DIR: str = "data/xml_backup"

    # Rotina diária cartão D-1 — com LOTE_AGUARDA_PIX_WEBHOOK=true vira fallback
    # (o disparo principal é o webhook PIX). Stone cartão só após 04:00 BRT.
    CARTAO_CRON_ENABLED: bool = False
    CARTAO_CRON_HOUR: int = 5
    CARTAO_CRON_MINUTE: int = 30
    # Segunda tentativa D-1 (mesmo dia anterior)
    CARTAO_CRON_RETRY_HOUR: int = 6
    CARTAO_CRON_RETRY_MINUTE: int = 0
    CARTAO_CRON_TZ: str = "America/Sao_Paulo"

    # Rotina diária PIX D-1 (solicita extrato; Stone entrega no webhook)
    # PIX: arquivo após ~03:00 do dia seguinte; alinhar >= 04:00.
    PIX_CRON_ENABLED: bool = False
    PIX_CRON_HOUR: int = 4
    PIX_CRON_MINUTE: int = 5
    PIX_CRON_RETRY_HOUR: int = 5
    PIX_CRON_RETRY_MINUTE: int = 5

    # true = cartão do dia só publica depois do webhook PIX (mesmo arquivo vazio).
    # Cron de cartão fica como fallback se o webhook não chegar.
    LOTE_AGUARDA_PIX_WEBHOOK: bool = True

    # Piloto: só publica estes seriais na fila (vazio = todos). Ex.: PB09231S72079
    # Vale para cartão (API/cron) e PIX (webhook). API ?terminal= sobrescreve.
    PUBLICAR_SOMENTE_SERIAIS: str = ""

    # Notifica auditoria do portal (tasy-insercao) sobre jobs do scheduler
    PORTAL_BASE_URL: str = "http://127.0.0.1:8001"
    PORTAL_INTERNAL_TOKEN: str = ""

    # Após cron cartão OK: agenda FECHAR dos recebimentos abertos (D-1) no portal.
    # Delay permite a fila RabbitMQ drenar antes da confirmação.
    FECHAR_RECEB_ENABLED: bool = False
    FECHAR_RECEB_DELAY_MINUTES: int = 45

    APP_NAME: str = "stone-extracao"
    APP_ENV: str = "homolog"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )


settings = Settings()
