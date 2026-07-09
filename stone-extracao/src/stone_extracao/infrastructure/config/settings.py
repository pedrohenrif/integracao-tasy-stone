from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # RabbitMQ
    RABBITMQ_URL: str = "amqp://stone:stone@localhost:5673/"
    RABBITMQ_QUEUE_CARTAO: str = "stone.cartao.transactions"
    RABBITMQ_EXCHANGE: str = "stone.direct"

    # Stone API — preencha STONE_API_TOKEN para homologação/produção
    STONE_MERCHANT_ID: str = "116852622"
    STONE_CONCILIATION_BASE_URL: str = "https://conciliation.stone.com.br/v2"
    STONE_API_TOKEN: str = ""

    # Fallback local (só se STONE_USE_SAMPLE=true)
    STONE_USE_SAMPLE: bool = False
    STONE_CARTAO_SAMPLE_PATH: str = "../stone_movimento_20260708_cartao.xml"

    APP_NAME: str = "stone-extracao"
    APP_ENV: str = "homolog"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
    )


settings = Settings()
