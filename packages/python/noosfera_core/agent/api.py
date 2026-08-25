"""API funcional de Sheily 0.2 para la consola personal y operacional."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from noosfera_core.agent.auth import AuthenticationError, AuthService
from noosfera_core.agent.documents import DocumentRejected, parse_upload
from noosfera_core.agent.events import EventPublisher, NatsEventPublisher, NullEventPublisher
from noosfera_core.agent.execution import (
    ExecutionGateway,
    InProcessExecutionGateway,
    RustExecutionClient,
)
from noosfera_core.agent.governance import (
    DeterministicGovernance,
    GovernanceEngine,
    OpaGovernance,
)
from noosfera_core.agent.model_provider import AgentModel, DeterministicLocalModel, OllamaModel
from noosfera_core.agent.models import (
    TERMINAL_STATUSES,
    ApprovalRequest,
    AuditEntry,
    Conversation,
    ConversationCreate,
    DocumentPublic,
    LoginRequest,
    MemoryRecord,
    Message,
    MessageCreate,
    Mission,
    MissionStatus,
    OperatorStatus,
    Principal,
    StopRequest,
    TokenResponse,
    new_id,
    utc_now,
)
from noosfera_core.agent.orchestrator import AgentOrchestrator, MissionConflict
from noosfera_core.agent.persistence import InMemoryStateStore, PostgresStateStore, StateStore
from noosfera_core.config import Settings
from noosfera_core.manifest import ServiceManifest, load_service_manifest
from noosfera_core.policy import OpaClient


@dataclass
class AgentContainer:
    settings: Settings
    manifest: ServiceManifest
    store: StateStore
    auth: AuthService
    orchestrator: AgentOrchestrator

    @classmethod
    def build(cls, settings: Settings, manifest: ServiceManifest) -> "AgentContainer":
        if settings.storage_backend == "memory":
            store: StateStore = InMemoryStateStore()
        elif settings.storage_backend == "postgres":
            store = PostgresStateStore(settings.database_url)
        else:
            raise ValueError("unsupported storage backend")

        if settings.event_backend == "disabled-test":
            events: EventPublisher = NullEventPublisher()
        elif settings.event_backend == "nats":
            events = NatsEventPublisher(settings.nats_url)
        else:
            raise ValueError("unsupported event backend")

        if settings.governance_backend == "deterministic-test":
            governance: GovernanceEngine = DeterministicGovernance()
        elif settings.governance_backend == "opa":
            governance = OpaGovernance(OpaClient(settings.opa_url))
        else:
            raise ValueError("unsupported governance backend")

        if settings.execution_backend == "in-process-test":
            execution: ExecutionGateway = InProcessExecutionGateway()
        elif settings.execution_backend == "rust":
            execution = RustExecutionClient(settings.execution_url)
        else:
            raise ValueError("unsupported execution backend")

        if settings.model_provider == "deterministic":
            model: AgentModel = DeterministicLocalModel()
        elif settings.model_provider == "ollama":
            model = OllamaModel(
                base_url=settings.model_base_url,
                model_name=settings.model_name,
                timeout_seconds=settings.model_timeout_seconds,
                max_input_chars=settings.model_max_input_chars,
                context_tokens=settings.model_context_tokens,
                output_tokens=settings.model_output_tokens,
                allow_remote=settings.model_allow_remote,
            )
        else:
            raise ValueError("unsupported model provider")

        auth = AuthService(
            username=settings.local_username,
            password=settings.local_password,
            secret=settings.token_secret,
            token_ttl_seconds=settings.token_ttl_seconds,
        )
        orchestrator = AgentOrchestrator(
            store=store,
            model=model,
            governance=governance,
            execution=execution,
            events=events,
            capability_secret=settings.capability_secret,
            capability_ttl_seconds=settings.capability_ttl_seconds,
            max_output_bytes=settings.max_output_bytes,
        )
        return cls(settings, manifest, store, auth, orchestrator)


def create_agent_app(
    manifest_path: str | Path,
    *,
    settings: Settings | None = None,
    container: AgentContainer | None = None,
) -> FastAPI:
    manifest = load_service_manifest(manifest_path)
    active_settings = settings or Settings()
    active_settings.assert_production_safe()
    runtime = container or AgentContainer.build(active_settings, manifest)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        del app
        await runtime.store.initialize()
        await runtime.orchestrator.events.connect()
        try:
            yield
        finally:
            await runtime.orchestrator.events.close()
            await runtime.store.close()

    app = FastAPI(
        title="Sheily local sovereign agent",
        version="0.2.0",
        description="Agente local-first con autorización humana y ejecución mediada por Rust.",
        lifespan=lifespan,
    )
    app.state.container = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in active_settings.cors_origins.split(",")],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def principal_from_authorization(
        authorization: Annotated[str | None, Header()] = None,
    ) -> Principal:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
            )
        try:
            return runtime.auth.verify(authorization.removeprefix("Bearer ").strip())
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    PrincipalDependency = Annotated[Principal, Depends(principal_from_authorization)]

    def require_operator(principal: PrincipalDependency) -> Principal:
        if principal.role not in {"operator", "admin"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="operator role required"
            )
        return principal

    OperatorDependency = Annotated[Principal, Depends(require_operator)]

    @app.get("/health/live")
    async def liveness() -> dict[str, Any]:
        return {"service": manifest.id, "version": "0.2.0", "status": "alive"}

    @app.get("/health/ready")
    async def readiness() -> dict[str, Any]:
        (
            model_ready,
            execution_ready,
            storage_ready,
            events_ready,
            policy_ready,
        ) = await asyncio.gather(
            runtime.orchestrator.model.health(),
            runtime.orchestrator.execution.health(),
            runtime.store.health(),
            runtime.orchestrator.events.health(),
            runtime.orchestrator.governance.health(),
        )
        checks = {
            "model": model_ready,
            "execution_kernel": execution_ready,
            "storage": storage_ready,
            "event_bus": events_ready,
            "policy_engine": policy_ready,
        }
        if not all(checks.values()):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=checks,
            )
        return {
            "service": manifest.id,
            "status": "ready",
            **checks,
        }

    @app.post("/v1/auth/login", response_model=TokenResponse)
    async def login(request: LoginRequest) -> TokenResponse:
        try:
            return runtime.auth.login(request.username, request.password)
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    @app.get("/v1/me", response_model=Principal)
    async def me(principal: PrincipalDependency) -> Principal:
        return principal

    @app.post("/v1/conversations", response_model=Conversation, status_code=201)
    async def create_conversation(
        request: ConversationCreate, principal: PrincipalDependency
    ) -> Conversation:
        conversation = Conversation(
            id=new_id("conversation"),
            user_id=principal.user_id,
            title=request.title,
            created_at=utc_now(),
        )
        await runtime.store.create_conversation(conversation)
        return conversation

    @app.get("/v1/conversations/{conversation_id}/messages", response_model=list[Message])
    async def list_messages(conversation_id: str, principal: PrincipalDependency) -> list[Message]:
        conversation = await runtime.store.get_conversation(conversation_id, principal.user_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        return await runtime.store.list_messages(conversation_id, principal.user_id)

    @app.post(
        "/v1/conversations/{conversation_id}/messages",
        response_model=Mission,
        status_code=202,
    )
    async def create_message(
        conversation_id: str,
        request: MessageCreate,
        background_tasks: BackgroundTasks,
        principal: PrincipalDependency,
    ) -> Mission:
        conversation = await runtime.store.get_conversation(conversation_id, principal.user_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        if len(set(request.document_ids)) != len(request.document_ids):
            raise HTTPException(status_code=422, detail="document ids must be unique")
        documents = await runtime.store.get_documents(request.document_ids, principal.user_id)
        if len(documents) != len(request.document_ids):
            raise HTTPException(status_code=404, detail="document not found")
        user_message = Message(
            id=new_id("message"),
            conversation_id=conversation_id,
            role="user",
            content=request.content,
            created_at=utc_now(),
        )
        await runtime.store.add_message(user_message)
        now = utc_now()
        mission = Mission(
            id=new_id("mission"),
            user_id=principal.user_id,
            conversation_id=conversation_id,
            prompt=request.content,
            document_ids=request.document_ids,
            remember=request.remember,
            status=MissionStatus.RECEIVED,
            created_at=now,
            updated_at=now,
        )
        await runtime.store.create_mission(mission)
        await runtime.store.append_event(
            mission.id,
            "mission.received",
            {"document_count": len(request.document_ids), "remember": request.remember},
        )
        background_tasks.add_task(runtime.orchestrator.plan, mission.id, principal.user_id)
        return mission

    @app.get("/v1/missions/{mission_id}", response_model=Mission)
    async def get_mission(mission_id: str, principal: PrincipalDependency) -> Mission:
        mission = await runtime.store.get_mission(mission_id, principal.user_id)
        if mission is None:
            raise HTTPException(status_code=404, detail="mission not found")
        return mission

    @app.post("/v1/missions/{mission_id}/approval", response_model=Mission, status_code=202)
    async def approve_mission(
        mission_id: str,
        request: ApprovalRequest,
        background_tasks: BackgroundTasks,
        principal: PrincipalDependency,
    ) -> Mission:
        mission = await runtime.store.get_mission(mission_id, principal.user_id)
        if mission is None:
            raise HTTPException(status_code=404, detail="mission not found")
        if mission.status != MissionStatus.AWAITING_APPROVAL:
            raise HTTPException(status_code=409, detail="mission is not waiting for approval")
        background_tasks.add_task(
            runtime.orchestrator.approve,
            mission_id,
            principal.user_id,
            approved=request.approved,
            remember_result=request.remember_result,
            reason=request.reason,
        )
        return mission

    @app.get("/v1/missions/{mission_id}/events")
    async def stream_events(
        mission_id: str,
        principal: PrincipalDependency,
        after: Annotated[int, Query(ge=0)] = 0,
    ) -> StreamingResponse:
        mission = await runtime.store.get_mission(mission_id, principal.user_id)
        if mission is None:
            raise HTTPException(status_code=404, detail="mission not found")

        async def generate() -> AsyncIterator[str]:
            sequence = after
            idle_ticks = 0
            while idle_ticks < 600:
                events = await runtime.store.list_events(mission_id, sequence)
                if events:
                    idle_ticks = 0
                    for event in events:
                        sequence = event.sequence
                        yield f"data: {event.model_dump_json()}\n\n"
                else:
                    idle_ticks += 1
                    yield ": keep-alive\n\n"
                latest = await runtime.store.get_mission(mission_id, principal.user_id)
                quiescent = TERMINAL_STATUSES | {MissionStatus.AWAITING_APPROVAL}
                if latest and latest.status in quiescent and not events:
                    break
                await asyncio.sleep(0.5)

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.post("/v1/documents", response_model=DocumentPublic, status_code=201)
    async def upload_document(
        principal: PrincipalDependency, upload: Annotated[UploadFile, File()]
    ) -> DocumentPublic:
        try:
            document = await parse_upload(
                upload, user_id=principal.user_id, max_bytes=active_settings.max_document_bytes
            )
        except DocumentRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        await runtime.store.save_document(document)
        return DocumentPublic(
            id=document.id,
            name=document.name,
            media_type=document.media_type,
            content_hash=document.content_hash,
            size_bytes=document.size_bytes,
            created_at=document.created_at,
        )

    @app.get("/v1/memories", response_model=list[MemoryRecord])
    async def list_memories(principal: PrincipalDependency) -> list[MemoryRecord]:
        return await runtime.store.list_memories(principal.user_id)

    @app.delete("/v1/memories/{memory_id}", status_code=204)
    async def delete_memory(memory_id: str, principal: PrincipalDependency) -> None:
        if not await runtime.store.delete_memory(memory_id, principal.user_id):
            raise HTTPException(status_code=404, detail="memory not found")

    @app.get("/v1/operator/audit", response_model=list[AuditEntry])
    async def audit(
        principal: OperatorDependency, limit: Annotated[int, Query(ge=1, le=1000)] = 200
    ) -> list[AuditEntry]:
        del principal
        return await runtime.store.list_audit(limit)

    @app.get("/v1/operator/status", response_model=OperatorStatus)
    async def operator_status(principal: OperatorDependency) -> OperatorStatus:
        del principal
        stop_active, _ = await runtime.store.get_stop()
        return OperatorStatus(
            stop_active=stop_active,
            model_provider=runtime.orchestrator.model.provider_name,
            model_name=runtime.orchestrator.model.model_name,
            storage_backend=runtime.store.backend_name,
            event_bus=runtime.orchestrator.events.name,
            policy_engine=runtime.orchestrator.governance.name,
            execution_kernel=runtime.orchestrator.execution.name,
        )

    @app.post("/v1/operator/stop", status_code=202)
    async def safe_stop(request: StopRequest, principal: OperatorDependency) -> dict[str, Any]:
        await runtime.orchestrator.execution.set_stop(request.active, request.reason)
        await runtime.store.set_stop(request.active, request.reason)
        await runtime.store.append_control_event(
            "safety.stop-changed",
            {
                "active": request.active,
                "reason": request.reason,
                "operator": principal.user_id,
            },
        )
        await runtime.orchestrator.events.publish(
            "safety.stop.v1",
            {
                "active": request.active,
                "reason": request.reason,
                "operator": principal.user_id,
                "timestamp": utc_now().isoformat(),
            },
        )
        return {"accepted": True, "active": request.active}

    @app.get("/v1/manifest")
    async def service_manifest(principal: PrincipalDependency) -> dict[str, Any]:
        del principal
        return manifest.model_dump(mode="json")

    @app.exception_handler(MissionConflict)
    async def mission_conflict_handler(_request: Any, exc: MissionConflict) -> Any:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=409, content={"detail": str(exc)})

    return app
