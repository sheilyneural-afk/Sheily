# Matriz de completitud

Esta matriz cierra Noosfera `0.3.0`. Una celda «definida» significa que existen archivos, propietario, contrato y verificación; no afirma que una capacidad del año 2300 sea tecnológicamente realizable hoy. La madurez individual está en `registry/module-maturity.yaml`.

| Área | Estado 0.3 | Evidencia principal |
|---|---|---|
| Perímetro | Cerrado | `SCOPE.md` |
| Arquitectura | Definida | `ARCHITECTURE.md`, `docs/architecture/` |
| 105 módulos | Registrados y clasificados por madurez | `registry/modules/`, `registry/module-maturity.yaml` |
| 14 servicios | Desplegables en referencia | `services/`, `deploy/services/` |
| Tipos de puerto | Cerrados por productor/consumidor | `registry/port-types.yaml` |
| Contratos | Versionados | `schemas/`, `proto/`, `api/` |
| Constitución | Texto y política | `docs/governance/`, `policies/constitution/` |
| Autorización | Política + kernel | `policies/authorization/`, `packages/rust/noosfera-capability/` |
| Ejecución | Kernel de unión real | `packages/rust/noosfera-execution-kernel/` |
| Identidad | Autoridad Ed25519 funcional | `agent/identity.py`, `services/identity-service/` |
| Memoria | Contrato, política y almacenamiento | `schemas/memory-record.schema.json`, `policies/privacy/`, `database/` |
| Auditoría | Append-only, recibos y anclas Merkle firmadas | `agent/audit_anchor.py`, `database/migrations/0009_immutable_audit.sql` |
| Federación | Contrato tolerante a demoras | `schemas/federation-package.schema.json`, `docs/architecture/federation.md` |
| Evolución | Política de etapas | `policies/evolution/`, `services/evolution-service/` |
| Seguridad | Amenazas y controles | `docs/security/`, `security/`, `.github/workflows/security.yml` |
| Observabilidad | Métricas, trazas, alertas, panel | `observability/` |
| Operación | SLO, runbooks, copias y DR | `ops/` |
| Local | Compose | `deploy/local/docker-compose.yml` |
| Producción | Helm base endurecida | `deploy/helm/noosfera/` |
| Consolas | Personal y operacional | `apps/` |
| Proveedores externos | Interfaces y referencias seguras | `adapters/`, `packages/python/noosfera_core/ports.py` |
| Pruebas | Arquitectura, contrato, integración, seguridad, recuperación y caos | `tests/` |
| Inventario de archivos | Cerrado y automático | `FILE_MANIFEST.yaml`, `tools/verify_repository.py` |
| Conversación local | Funcional | `packages/python/noosfera_core/agent/`, `tests/agent/` |
| LLM local | Funcional y configurable | `agent/model_provider.py`, `docs/adr/0009-local-first-model-runtime.md` |
| Análisis documental | Funcional para texto y PDF | `agent/documents.py`, `schemas/agent-mission.schema.json` |
| Aprobación humana | Funcional | `agent/orchestrator.py`, `apps/personal-console/` |
| Herramientas limitadas | Funcional en Rust | `packages/rust/noosfera-execution-service/` |
| Memoria consentida | Funcional | `database/migrations/0007_agent_runtime.sql`, `policies/privacy/memory_write.rego` |
| Streaming | Funcional mediante SSE | `agent/api.py`, `apps/personal-console/src/api.ts` |
| Cognición anterior al LLM | Funcional y persistente | `agent/cognition.py`, `tests/agent/test_cognitive_kernel.py` |
| Agency independiente | Plan atestado Ed25519 | `agent/agency.py`, `services/agency-service/` |
| Governance independiente | Único emisor de capacidades | `agent/governance_authority.py`, `services/governance-service/` |
| Anti-replay | Durable y compartido | `execution_capability_ledger`, ejecutor Rust |
| Parada operacional | Firmada, monotónica y durable | ejecutor Rust, `tests/agent/test_api_flow.py` |
| Revocación | Firmada y durable | `execution_revocations`, ejecutor Rust |
| E2E multiproceso | Automatizado | `.github/workflows/e2e.yml`, `tools/run_local_e2e.py` |

## No implementado deliberadamente

- AGI o conciencia artificial.
- Simulación física total.
- Interfaces neuronales reales.
- Actuadores físicos reales.
- Biofabricación.
- Infraestructura vital.

Para estas capacidades existen puertos y controles. Conectarlas exige un proveedor nuevo, ADR, amenaza, pruebas y autorización; no se permiten falsos proveedores que aparenten una capacidad inexistente.
