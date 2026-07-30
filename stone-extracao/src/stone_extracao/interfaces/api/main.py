from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, HttpUrl

from stone_extracao.application.services.data_referencia import data_ontem
from stone_extracao.application.use_cases.extrair_conciliacao_cartao import (
    ExtracaoResultado,
    ExtrairConciliacaoCartao,
)
from stone_extracao.application.use_cases.receber_webhook_pix import (
    ReceberWebhookPix,
    extract_download_url,
    parse_webhook_payload,
)
from stone_extracao.application.use_cases.solicitar_extrato_pix import SolicitarExtratoPix
from stone_extracao.infrastructure.config.logging import get_logger, setup_logging
from stone_extracao.infrastructure.config.settings import settings
from stone_extracao.infrastructure.messaging.rabbit import (
    RabbitPublisher,
    close_rabbitmq,
    connect_rabbitmq,
    declare_topology,
)
from stone_extracao.infrastructure.parsers.cartao_parser import CartaoXmlParser
from stone_extracao.infrastructure.parsers.pix_parser import PixCsvParser
from stone_extracao.infrastructure.scheduling.cartao_diario import (
    aplicar_estado_inicial,
    criar_scheduler_cartao,
    set_cron_enabled,
    status_cron,
)
from stone_extracao.infrastructure.stone.conciliation_client import (
    StoneConciliationClient,
    StoneFetchError,
)
from stone_extracao.infrastructure.stone.pix_client import PixFetchError, StonePixClient
from stone_extracao.infrastructure.store.ultima_extracao import salvar_extracao
from stone_extracao.interfaces.api.painel import router as painel_router

logger = get_logger(__name__)


async def executar_extracao_cartao(
    publisher: RabbitPublisher,
    reference_date: str,
) -> ExtracaoResultado:
    """Caminho único: API manual, D-1 e cron diário."""
    use_case = ExtrairConciliacaoCartao(
        stone_client=StoneConciliationClient(),
        parser=CartaoXmlParser(),
        publisher=publisher,
    )
    result = await use_case.execute(reference_date)
    salvar_extracao(
        reference_date=result.reference_date,
        source=result.source,
        published_count=result.published_count,
        transactions=result.transactions,
    )
    return result


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    connection = await connect_rabbitmq()
    channel = await connection.channel()
    await declare_topology(channel)
    app.state.rabbit_connection = connection
    app.state.rabbit_channel = channel
    app.state.publisher = RabbitPublisher(channel)

    async def _cron_runner(reference_date: str) -> ExtracaoResultado:
        return await executar_extracao_cartao(app.state.publisher, reference_date)

    scheduler = criar_scheduler_cartao(_cron_runner)
    app.state.scheduler = scheduler
    scheduler.start()
    aplicar_estado_inicial(scheduler)

    yield

    scheduler.shutdown(wait=False)
    await close_rabbitmq(connection)


app = FastAPI(
    title="stone-extracao",
    description=(
        "Producer: extrai conciliação Stone (Cartão batch + PIX webhook), "
        "valida e publica no RabbitMQ. Não grava no Tasy."
    ),
    version="0.2.0",
    lifespan=lifespan,
)
app.include_router(painel_router)


class ConciliationResponse(BaseModel):
    reference_date: str
    source: str
    parsed_count: int
    published_count: int
    queue: str
    sample_ids: list[str] = Field(default_factory=list)
    mode: str = "manual"


class PixRequestResponse(BaseModel):
    reference_date: str
    status: str
    source: str
    message: str
    published_from_body: int = 0
    queue: str = ""


class PixWebhookResponse(BaseModel):
    source: str
    parsed_count: int
    published_count: int
    queue: str
    sample_ids: list[str] = Field(default_factory=list)
    event_type: str = "pix"
    status: str = "processed"
    reference_date: str | None = None


class PixWebhookRegisterBody(BaseModel):
    url: HttpUrl = Field(..., description="URL HTTPS pública do POST /pix/webhook")


class PixWebhookRegisterResponse(BaseModel):
    status: str
    http_status: int
    webhook_url: str
    message: str


def _publisher(request: Request) -> RabbitPublisher:
    publisher = getattr(request.app.state, "publisher", None)
    if publisher is None:
        raise HTTPException(status_code=503, detail="RabbitMQ não conectado")
    return publisher


def _to_response(result: ExtracaoResultado, *, mode: str) -> ConciliationResponse:
    return ConciliationResponse(
        reference_date=result.reference_date,
        source=result.source,
        parsed_count=result.parsed_count,
        published_count=result.published_count,
        queue=settings.RABBITMQ_QUEUE_CARTAO,
        sample_ids=result.sample_ids,
        mode=mode,
    )


@app.get("/health")
async def health(request: Request):
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "env": settings.APP_ENV,
        "stone_token_configured": bool(settings.STONE_API_TOKEN),
        "use_sample": settings.STONE_USE_SAMPLE,
        "queues": {
            "cartao": settings.RABBITMQ_QUEUE_CARTAO,
            "pix": settings.RABBITMQ_QUEUE_PIX,
        },
        "pix_merchant_id": settings.STONE_PIX_MERCHANT_ID,
        "cartao_cron": status_cron(getattr(request.app.state, "scheduler", None)),
    }


@app.get("/scheduler/cartao")
async def get_scheduler_cartao(request: Request):
    """Status do cron D-1 (ligado/desligado pelo painel)."""
    return status_cron(getattr(request.app.state, "scheduler", None))


class SchedulerToggleBody(BaseModel):
    enabled: bool


@app.post("/scheduler/cartao")
async def post_scheduler_cartao(body: SchedulerToggleBody, request: Request):
    """Ativa ou pausa o cron cartão D-1 (persistido entre restarts)."""
    scheduler = getattr(request.app.state, "scheduler", None)
    return set_cron_enabled(scheduler, body.enabled)


@app.post("/cartao/conciliation", response_model=ConciliationResponse)
async def ingest_cartao(
    request: Request,
    date: str = Query(..., pattern=r"^\d{8}$", description="YYYYMMDD"),
):
    """Extrato Cartão: busca ativa na API Stone e publica 1 msg/tx."""
    publisher = _publisher(request)
    try:
        result = await executar_extracao_cartao(publisher, date)
    except StoneFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(result, mode="manual")


@app.post("/cartao/conciliation/d-1", response_model=ConciliationResponse)
async def ingest_cartao_d1(request: Request):
    """
    Rotina de produção (manual): extrai **sempre o dia anterior** (D-1)
    no fuso America/Sao_Paulo e publica todas as transações na fila.
    """
    reference_date = data_ontem(settings.CARTAO_CRON_TZ)
    logger.info("Extração cartão D-1 (manual) | date=%s", reference_date)
    publisher = _publisher(request)
    try:
        result = await executar_extracao_cartao(publisher, reference_date)
    except StoneFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(result, mode="d-1")


@app.post("/pix/conciliation/request", response_model=PixRequestResponse)
async def request_pix_extract(
    request: Request,
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD"),
):
    """
    Passo 1 do PIX: solicita o extrato na Stone.
    Em seguida a Stone envia o arquivo no webhook público POST /pix/webhook.
    """
    publisher = _publisher(request)
    use_case = SolicitarExtratoPix(
        pix_client=StonePixClient(),
        parser=PixCsvParser(),
        publisher=publisher,
    )
    try:
        result = await use_case.execute(date)
    except PixFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PixRequestResponse(
        reference_date=result.reference_date,
        status=result.status,
        source=result.source,
        message=result.message,
        published_from_body=result.published_from_body,
        queue=settings.RABBITMQ_QUEUE_PIX if result.published_from_body else "",
    )


async def _process_pix_webhook_body(publisher: RabbitPublisher, body: bytes) -> None:
    """Download/parse/publish em background (Stone exige HTTP 200 em ≤5s)."""
    use_case = ReceberWebhookPix(
        parser=PixCsvParser(),
        publisher=publisher,
        downloader=StonePixClient(),
    )
    try:
        result = await use_case.execute(body, source="webhook")
        logger.info(
            "Webhook PIX processado | type=%s | parsed=%s | published=%s",
            result.event_type,
            result.parsed_count,
            result.published_count,
        )
    except Exception:
        logger.exception("Webhook PIX | falha no processamento em background")


@app.post("/pix/webhook/register", response_model=PixWebhookRegisterResponse)
async def register_pix_webhook(body: PixWebhookRegisterBody):
    """
    Cadastra a URL HTTPS do webhook na Stone (POST /v2/webhook).
    A Stone chama POST /pix/webhook com {"type":"validation_notification"} — deve responder 2xx em ≤3s.
    """
    client = StonePixClient()
    try:
        result = await client.register_webhook(str(body.url))
    except PixFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PixWebhookRegisterResponse(
        status=str(result["status"]),
        http_status=int(result["http_status"]),
        webhook_url=str(result["webhook_url"]),
        message=str(result["message"]),
    )


@app.put("/pix/webhook/register", response_model=PixWebhookRegisterResponse)
async def update_pix_webhook(body: PixWebhookRegisterBody):
    """Atualiza a URL HTTPS do webhook na Stone (PUT /v2/webhook)."""
    client = StonePixClient()
    try:
        result = await client.update_webhook(str(body.url))
    except PixFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PixWebhookRegisterResponse(
        status=str(result["status"]),
        http_status=int(result["http_status"]),
        webhook_url=str(result["webhook_url"]),
        message=str(result["message"]),
    )


@app.post("/pix/webhook", response_model=PixWebhookResponse)
async def pix_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_stone_signature: str | None = Header(default=None, alias="X-Stone-Signature"),
):
    """
    Endpoint público HTTPS para a Stone.

    - validation_notification → 200 imediato (cadastro)
    - type=pix + downloadUrl/url → 200 imediato + download/parse em background
    - CSV cru (legado/homolog) → processa síncrono
    """
    if settings.PIX_WEBHOOK_SECRET and x_stone_signature != settings.PIX_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Assinatura do webhook inválida")

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Body vazio")

    payload = parse_webhook_payload(body)
    if payload is not None:
        event_type = str(payload.get("type") or "").strip().lower()
        if event_type == "validation_notification":
            return PixWebhookResponse(
                source="webhook",
                parsed_count=0,
                published_count=0,
                queue=settings.RABBITMQ_QUEUE_PIX,
                event_type="validation_notification",
                status="ok",
            )

        if extract_download_url(payload) or event_type == "pix":
            if event_type == "pix" and not extract_download_url(payload):
                raise HTTPException(
                    status_code=422,
                    detail="Notificação PIX sem downloadUrl/url",
                )
            publisher = _publisher(request)
            background_tasks.add_task(_process_pix_webhook_body, publisher, body)
            return PixWebhookResponse(
                source="webhook",
                parsed_count=0,
                published_count=0,
                queue=settings.RABBITMQ_QUEUE_PIX,
                event_type=event_type or "pix",
                status="accepted",
                reference_date=str(
                    payload.get("referenceDate") or payload.get("reference_date") or ""
                )
                or None,
            )

    publisher = _publisher(request)
    use_case = ReceberWebhookPix(
        parser=PixCsvParser(),
        publisher=publisher,
        downloader=StonePixClient(),
    )
    try:
        result = await use_case.execute(body, source="webhook")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Falha ao processar webhook PIX: {exc}") from exc

    return PixWebhookResponse(
        source=result.source,
        parsed_count=result.parsed_count,
        published_count=result.published_count,
        queue=settings.RABBITMQ_QUEUE_PIX,
        sample_ids=result.sample_ids,
        event_type=result.event_type,
        status=result.status,
        reference_date=result.reference_date,
    )


@app.post("/pix/conciliation/dev", response_model=PixWebhookResponse)
async def pix_dev_from_sample(
    request: Request,
    limit: int | None = Query(
        default=None,
        ge=1,
        le=5000,
        description="Publica no máximo N txs (útil no 1º teste)",
    ),
    terminal: str | None = Query(
        default=None,
        description="Filtra serial(is). Vários separados por vírgula",
    ),
    only_seeded: bool = Query(
        default=True,
        description="Se true, só terminais do seed Cotolengo (evita DLQ de serial desconhecido)",
    ),
):
    """
    Dev/homolog: lê o sample CSV local e publica na fila PIX (sem webhook Stone).
    Default: only_seeded=true (terminais já cadastrados em maquininha_stone).
    """
    publisher = _publisher(request)
    client = StonePixClient()
    try:
        raw = client.read_sample()
    except PixFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Seriais ativos do seed Cotolengo (homolog)
    seeded = {
        "PB09243M78791",
        "PB09231S72079",
        "PB0921B473408",
        "4AJ45HT4D",
        "PB09243J71219",
        "PB0921B977799",
    }
    terminals: set[str] | None = None
    if terminal:
        terminals = {t.strip() for t in terminal.split(",") if t.strip()}
    elif only_seeded:
        terminals = seeded

    use_case = ReceberWebhookPix(parser=PixCsvParser(), publisher=publisher)
    result = await use_case.execute(
        raw, source="sample", terminals=terminals, limit=limit
    )
    return PixWebhookResponse(
        source=result.source,
        parsed_count=result.parsed_count,
        published_count=result.published_count,
        queue=settings.RABBITMQ_QUEUE_PIX,
        sample_ids=result.sample_ids,
    )
