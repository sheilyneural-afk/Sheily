# Matriz de completitud

Esta matriz cierra Noosfera `0.1.0`. Una celda «definida» significa que existen archivos, propietario, contrato y verificación; no afirma que una capacidad del año 2300 sea tecnológicamente realizable hoy.

| Área | Estado 0.1 | Evidencia principal |
|---|---|---|
| Perímetro | Cerrado | `SCOPE.md` |
| Arquitectura | Definida | `ARCHITECTURE.md`, `docs/architecture/` |
| 105 módulos | Registrados | `registry/modules/` |
| 14 servicios | Desplegables en referencia | `services/`, `deploy/services/` |
| Tipos de puerto | Cerrados por productor/consumidor | `registry/port-types.yaml` |
| Contratos | Versionados | `schemas/`, `proto/`, `api/` |
| Constitución | Texto y política | `docs/governance/`, `policies/constitution/` |
| Autorización | Política + kernel | `policies/authorization/`, `packages/rust/noosfera-capability/` |
| Ejecución | Kernel de unión real | `packages/rust/noosfera-execution-kernel/` |
| Identidad | Contrato y dominio | `proto/noosfera/identity/`, `services/identity-service/` |
| Memoria | Contrato, política y almacenamiento | `schemas/memory-record.schema.json`, `policies/privacy/`, `database/` |
| Auditoría | Recibos encadenados | `packages/python/noosfera_core/audit.py`, `database/migrations/0004_audit.sql` |
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

## No implementado deliberadamente

- AGI o conciencia artificial.
- Simulación física total.
- Interfaces neuronales reales.
- Actuadores físicos reales.
- Biofabricación.
- Infraestructura vital.

Para estas capacidades existen puertos y controles. Conectarlas exige un proveedor nuevo, ADR, amenaza, pruebas y autorización; no se permiten falsos proveedores que aparenten una capacidad inexistente.
