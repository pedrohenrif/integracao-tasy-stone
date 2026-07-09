from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus


class Settings(BaseSettings):
    # RabbitMQ
    RABBITMQ_URL: str = "amqp://stone:stone@localhost:5673/"
    RABBITMQ_QUEUE_CARTAO: str = "stone.cartao.transactions"

    # Stone
    STONE_MERCHANT_ID: str = "116852622"
    STONE_CONCILIATION_BASE_URL: str = "https://conciliation.stone.com.br/v2"
    STONE_API_TOKEN: str = ""
    STONE_CARTAO_SAMPLE_PATH: str = "../stone_movimento_20260708_cartao.xml"

    # GMAIL (fase futura)
    GMAIL_USER: str = ""
    GMAIL_PASS: str = ""

    # POSTGRES (fase futura)
    POSTGRES_USER: str = ""
    POSTGRES_PASS: str = ""
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = ""

    # ORACLE Tasy
    ORACLE_USER: str = ""
    ORACLE_PASS: str = ""
    ORACLE_DSN: str = ""

    @computed_field
    @property
    def ASYNC_POSTGRES_URL(self) -> str:
        user = self.POSTGRES_USER
        password = quote_plus(self.POSTGRES_PASS)
        host = self.POSTGRES_HOST
        port = self.POSTGRES_PORT
        db = self.POSTGRES_DB
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )


settings = Settings()
