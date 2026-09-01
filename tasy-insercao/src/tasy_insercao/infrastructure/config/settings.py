from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # RabbitMQ
    RABBITMQ_URL: str = "amqp://stone:stone@localhost:5673/"
    RABBITMQ_QUEUE_CARTAO: str = "stone.cartao.transactions"
    RABBITMQ_QUEUE_RETRY: str = "stone.cartao.transactions.retry"
    RABBITMQ_QUEUE_DLQ: str = "stone.cartao.transactions.dlq"
    RABBITMQ_QUEUE_PIX: str = "stone.pix.transactions"
    RABBITMQ_QUEUE_PIX_RETRY: str = "stone.pix.transactions.retry"
    RABBITMQ_QUEUE_PIX_DLQ: str = "stone.pix.transactions.dlq"
    RABBITMQ_EXCHANGE: str = "stone.direct"

    # Retry / anti-perda
    RETRY_MAX_ATTEMPTS: int = 5
    RETRY_DELAYS_SECONDS: str = "30,60,120,300,600"  # backoff por tentativa
    # Timeout do insert Oracle por mensagem (evita travar prefetch=1 a madrugada inteira)
    CONSUMER_HANDLER_TIMEOUT_SECONDS: int = 180
    # Log periódico confirmando que o consumer está vivo e à escuta
    CONSUMER_HEARTBEAT_SECONDS: int = 300
    CONSUMER_RECONNECT_DELAY_SECONDS: int = 5

    # Postgres staging
    POSTGRES_USER: str = ""
    POSTGRES_PASS: str = ""
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = ""

    # Oracle Tasy
    ORACLE_USER: str = ""
    ORACLE_PASS: str = ""
    ORACLE_DSN: str = ""
    # Sessão Tasy antes do FECHAR_CAIXA_RECEB (CTB online exige perfil ativo)
    # ADM DO SISTEMA = 1848; stone também tem FINANCEIRO - ANALISTA = 2351
    TASY_NM_USUARIO: str = "stone"
    TASY_CD_ESTABELECIMENTO: int = 1
    TASY_CD_PERFIL: int = 1848

    # Portal de controle (React + JWT)
    PORTAL_JWT_SECRET: str = "altere-este-secret-em-producao"
    PORTAL_JWT_EXPIRE_HOURS: int = 12
    PORTAL_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    PORTAL_ADMIN_USER: str = "admin"
    PORTAL_ADMIN_PASS: str = "admin123"
    RABBITMQ_MGMT_URL: str = "http://localhost:15673"
    RABBITMQ_MGMT_USER: str = "stone"
    RABBITMQ_MGMT_PASS: str = "stone"

    # stone-extracao (reprocessar dia via POST /cartao/conciliation)
    STONE_EXTRACAO_BASE_URL: str = "http://localhost:8000"

    # Token interno para stone-extracao gravar eventos de scheduler na auditoria
    PORTAL_INTERNAL_TOKEN: str = ""

    # FECHAR o recebimento unificado (1 por caixa) apos quiet period sem novo cartao/PIX.
    # Cada insert remarca o timer — so confirma depois que o lote (cartao+PIX) assentou.
    FECHAR_APOS_LOTE_ENABLED: bool = True
    FECHAR_APOS_LOTE_SECONDS: int = 300  # 5 min apos o ultimo insert nesse recebimento
    # Antes do FECHAR: exige staging do caixa/dia sem pendente/retry/processando (1,2,6,9).
    FECHAR_REQUIRE_STAGING_OK: bool = True
    # Antes do FECHAR: se stone-extracao ainda aguarda webhook PIX do dia, adia.
    FECHAR_REQUIRE_LOTE_PIX_OK: bool = True
    # Quantas vezes pode adiar o FECHAR (quiet period de novo) antes de forçar.
    FECHAR_MAX_ADIAMENTOS: int = 12  # 12 * 5min ~= 1h

    APP_NAME: str = "tasy-insercao"
    APP_ENV: str = "homolog"

    @property
    def portal_cors_origins(self) -> list[str]:
        return [o.strip() for o in self.PORTAL_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{quote_plus(self.POSTGRES_PASS)}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def retry_delays(self) -> list[int]:
        return [int(x.strip()) for x in self.RETRY_DELAYS_SECONDS.split(",") if x.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )


settings = Settings()
