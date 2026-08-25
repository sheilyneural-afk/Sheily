"""API de experiencia de Sheily 0.3; orquesta autoridades separadas."""

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

from noosfera_core.agent.agency import AgencyAuthority, AgencyGateway, RemoteAgencyClient
from noosfera_core.agent.auth import AuthenticationError
from noosfera_core.agent.cognition import CognitionGateway, CognitiveKernel, RemoteCognitionClient
from noosfera_core.agent.crypto import Ed25519Signer, Ed25519Verifier
from noosfera_core.agent.document_verification import (
    DocumentEvidenceVerifier,
    DocumentVerificationGateway,
    RemoteDocumentVerificationClient,
)
from noosfera_core.agent.documents import DocumentRejected, parse_upload
from noosfera_core.agent.events import EventPublisher, NatsEventPublisher, NullEventPublisher
from noosfera_core.agent.execution import (
    ExecutionGateway,
    ExecutionRejected,
    InProcessExecutionGateway,
    RustExecutionClient,
)
from noosfera_core.agent.governance import DeterministicGovernance
from noosfera_core.agent.governance_authority import (
    GovernanceAuthority,
    GovernanceGateway,
    GovernanceStore,
    RemoteGovernanceClient,
)
from noosfera_core.agent.identity import (
    IdentityAuthority,
    IdentityGateway,
    RemoteIdentityClient,
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
    RevocationRequest,
    StopRequest,
    TokenResponse,
    new_id,
    utc_now,
)
from noosfera_core.agent.orchestrator import AgentOrchestrator, MissionConflict
from noosfera_core.agent.persistence import InMemoryStateStore, PostgresStateStore, StateStore
from noosfera_core.agent.self_model import (
    RegistrySelfModel,
    SelfModelSnapshot,
    parse_runtime_registry_urls,
)
from noosfera_core.config import Settings
from noosfera_core.hashing import canonical_hash
from noosfera_core.manifest import ServiceManifest, load_service_manifest
from noosfera_core.module_registry import install_runtime_module_registry


@dataclass
class AgentContainer:
    settings: Settings
    manifest: ServiceManifest
    store: StateStore
    identity: IdentityGateway
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

        if settings.identity_backend == "in-process-test":
            identity: IdentityGateway = IdentityAuthority(
                username=settings.local_username,
                password=settings.local_password,
                signer=Ed25519Signer(
                    settings.identity_private_key_b64, key_id=settings.identity_key_id
                ),
                token_ttl_seconds=settings.token_ttl_seconds,
            )
        elif settings.identity_backend == "remote":
            identity = RemoteIdentityClient(
                settings.identity_url,
                public_key_b64=settings.identity_public_key_b64,
                key_id=settings.identity_key_id,
            )
        else:
            raise ValueError("unsupported identity backend")

        if settings.cognition_backend == "in-process-test":
            cognition: CognitionGateway = CognitiveKernel(
                self_model=RegistrySelfModel(
                    registry_path=settings.self_model_registry_path,
                    node_id=settings.node_id,
                    current_manifest=manifest,
                    service_urls=parse_runtime_registry_urls(settings.runtime_registry_urls),
                    timeout_seconds=settings.runtime_registry_timeout_seconds,
                    cache_seconds=settings.self_model_cache_seconds,
                )
            )
        elif settings.cognition_backend == "remote":
            cognition = RemoteCognitionClient(
                settings.cognition_url, service_token=settings.internal_service_token
            )
        else:
            raise ValueError("unsupported cognition backend")

        if settings.agency_backend == "in-process-test":
            agency: AgencyGateway = AgencyAuthority(
                Ed25519Signer(settings.agency_private_key_b64, key_id=settings.agency_key_id)
            )
        elif settings.agency_backend == "remote":
            agency = RemoteAgencyClient(
                settings.agency_url, service_token=settings.internal_service_token
            )
        else:
            raise ValueError("unsupported agency backend")

        if settings.governance_backend == "deterministic-test":
            governance: GovernanceGateway = GovernanceAuthority(
                policy=DeterministicGovernance(),
                signer=Ed25519Signer(
                    settings.governance_private_key_b64, key_id=settings.governance_key_id
                ),
                agency_verifier=Ed25519Verifier(
                    settings.agency_public_key_b64, key_id=settings.agency_key_id
                ),
                identity_verifier=Ed25519Verifier(
                    settings.identity_public_key_b64, key_id=settings.identity_key_id
                ),
                store=GovernanceStore(),
                capability_ttl_seconds=settings.capability_ttl_seconds,
            )
        elif settings.governance_backend == "remote":
            governance = RemoteGovernanceClient(
                settings.governance_url, service_token=settings.internal_service_token
            )
        else:
            raise ValueError("unsupported governance backend")

        if settings.execution_backend == "in-process-test":
            execution: ExecutionGateway = InProcessExecutionGateway(
                governance_public_key_b64=settings.governance_public_key_b64,
                governance_key_id=settings.governance_key_id,
            )
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
                max_concurrency=settings.model_max_concurrency,
                allow_remote=settings.model_allow_remote,
            )
        else:
            raise ValueError("unsupported model provider")

        if settings.document_verification_backend == "in-process-test":
            document_verifier: DocumentVerificationGateway = DocumentEvidenceVerifier(
                Ed25519Signer(settings.audit_private_key_b64, key_id=settings.audit_key_id)
            )
        elif settings.document_verification_backend == "remote":
            document_verifier = RemoteDocumentVerificationClient(
                settings.audit_url, service_token=settings.internal_service_token
            )
        else:
            raise ValueError("unsupported document verification backend")

        orchestrator = AgentOrchestrator(
            store=store,
            model=model,
            cognition=cognition,
            agency=agency,
            governance=governance,
            identity=identity,
            execution=execution,
            document_verifier=document_verifier,
            audit_signature_verifier=Ed25519Verifier(
                settings.audit_public_key_b64, key_id=settings.audit_key_id
            ),
            events=events,
            max_output_bytes=settings.max_output_bytes,
            model_max_input_chars=settings.model_max_input_chars,
            model_document_max_blocks=settings.model_document_max_blocks,
            model_context_tokens=settings.model_context_tokens,
            model_output_tokens=settings.model_output_tokens,
        )
        return cls(settings, manifest, store, identity, orchestrator)


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
        if isinstance(runtime.orchestrator.governance, GovernanceAuthority):
            await runtime.orchestrator.governance.initialize()
        await runtime.orchestrator.events.connect()
        try:
            yield
        finally:
            await runtime.orchestrator.events.close()
            if isinstance(runtime.orchestrator.governance, GovernanceAuthority):
                await runtime.orchestrator.governance.close()
            await runtime.store.close()

    app = FastAPI(
        title="Sheily local sovereign agent",
        version="0.3.0",
        description="Agente cognitivo local con autoridades independientes y ejecución Rust.",
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
            return runtime.identity.verify_access_token(
                authorization.removeprefix("Bearer ").strip()
            )
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
        return {"service": manifest.id, "version": "0.3.0", "status": "alive"}

    @app.get("/health/ready")
    async def readiness() -> dict[str, Any]:
        (
            model_ready,
            identity_ready,
            cognition_ready,
            agency_ready,
            governance_ready,
            execution_ready,
            document_verifier_ready,
            storage_ready,
            events_ready,
        ) = await asyncio.gather(
            runtime.orchestrator.model.health(),
            runtime.identity.health(),
            runtime.orchestrator.cognition.health(),
            runtime.orchestrator.agency.health(),
            runtime.orchestrator.governance.health(),
            runtime.orchestrator.execution.health(),
            runtime.orchestrator.document_verifier.health(),
            runtime.store.health(),
            runtime.orchestrator.events.health(),
        )
        checks = {
            "model": model_ready,
            "identity_authority": identity_ready,
            "cognitive_kernel": cognition_ready,
            "agency_authority": agency_ready,
            "governance_authority": governance_ready,
            "execution_kernel": execution_ready,
            "document_verifier": document_verifier_ready,
            "storage": storage_ready,
            "event_bus": events_ready,
        }
        if not all(checks.values()):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=checks,
            )
        return {
            "service": manifest.id,
            "status": "ready",
            "model_provider": runtime.orchestrator.model.provider_name,
            "model_name": runtime.orchestrator.model.model_name,
            **checks,
        }

    @app.post("/v1/auth/login", response_model=TokenResponse)
    async def login(request: LoginRequest) -> TokenResponse:
        try:
            return await runtime.identity.login(request.username, request.password)
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    @app.get("/v1/me", response_model=Principal)
    async def me(principal: PrincipalDependency) -> Principal:
        return principal

    @app.get("/v1/self-model", response_model=SelfModelSnapshot)
    async def self_model(principal: PrincipalDependency) -> SelfModelSnapshot:
        del principal
        return await runtime.orchestrator.cognition.inspect_self(force_refresh=True)

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
        authorization: Annotated[str | None, Header()] = None,
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
            access_token=(authorization or "").removeprefix("Bearer ").strip(),
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
            normalized_hash=document.normalized_hash,
            version_id=document.version_id,
            block_count=len(document.blocks),
            page_count=max(
                (block.page_number or 1 for block in document.blocks), default=1
            ),
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
    async def safe_stop(
        request: StopRequest,
        principal: OperatorDependency,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        directive_hash = canonical_hash({"active": request.active, "reason": request.reason})
        approval = await runtime.identity.approve(
            token=(authorization or "").removeprefix("Bearer ").strip(),
            mission_id="urn:noosfera:mission:operator-control",
            plan_hash=directive_hash,
            approved=True,
            remember_result=False,
            reason=request.reason,
        )
        directive = await runtime.orchestrator.governance.issue_stop(
            active=request.active, reason=request.reason, approval=approval
        )
        try:
            await runtime.orchestrator.execution.set_stop(directive)
        except ExecutionRejected as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        await runtime.store.set_stop(request.active, request.reason)
        await runtime.store.append_control_event(
            "safety.stop-changed",
            {
                "active": request.active,
                "reason": request.reason,
                "operator": principal.user_id,
                "directive_id": directive.id,
                "directive_version": directive.version,
            },
        )
        await runtime.orchestrator.events.publish(
            "safety.stop.v1",
            {
                "active": request.active,
                "reason": request.reason,
                "operator": principal.user_id,
                "timestamp": utc_now().isoformat(),
                "directive_id": directive.id,
            },
        )
        return {"accepted": True, "active": request.active}

    @app.post("/v1/operator/capabilities/{capability_id}/revoke", status_code=202)
    async def revoke_capability(
        capability_id: str,
        request: RevocationRequest,
        principal: OperatorDependency,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        directive_hash = canonical_hash({"capability_id": capability_id, "reason": request.reason})
        approval = await runtime.identity.approve(
            token=(authorization or "").removeprefix("Bearer ").strip(),
            mission_id="urn:noosfera:mission:operator-control",
            plan_hash=directive_hash,
            approved=True,
            remember_result=False,
            reason=request.reason,
        )
        directive = await runtime.orchestrator.governance.issue_revocation(
            capability_id=capability_id,
            reason=request.reason,
            approval=approval,
        )
        await runtime.orchestrator.execution.revoke(directive)
        await runtime.store.append_control_event(
            "capability.revoked",
            {
                "capability_id": capability_id,
                "reason": request.reason,
                "operator": principal.user_id,
                "directive_id": directive.id,
                "directive_version": directive.version,
            },
        )
        await runtime.orchestrator.events.publish(
            "authorization.revocation.v1",
            directive.model_dump(mode="json"),
        )
        return {"accepted": True, "capability_id": capability_id}

    @app.get("/v1/manifest")
    async def service_manifest(principal: PrincipalDependency) -> dict[str, Any]:
        del principal
        return manifest.model_dump(mode="json")

    @app.exception_handler(MissionConflict)
    async def mission_conflict_handler(_request: Any, exc: MissionConflict) -> Any:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=409, content={"detail": str(exc)})

    return install_runtime_module_registry(app, manifest)
