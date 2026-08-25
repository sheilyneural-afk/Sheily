# Noosfera

Repositorio de referencia para convertir la arquitectura conceptual **Noosfera 2300** en un sistema construible, verificable y evolutivo. La versión 0.2 añade **Sheily**, un agente local funcional para conversación y análisis de documentos.

Este repositorio no afirma implementar una superinteligencia ni tecnología inexistente. Implementa el **plano de control real** y un primer recorrido ejecutable: límites de confianza, contratos, módulos lógicos, servicios, políticas, inferencia local, kernel Rust, persistencia, consolas, observabilidad y pruebas.

## Estado

- Versión de arquitectura: `0.2.0`
- Agente funcional: conversación y análisis documental con Ollama local
- Autoridad de ejecución: kernel Rust con dos herramientas puras permitidas
- Módulos lógicos registrados: `105`
- Dominios de servicio: `14`
- Circuitos operativos: `6`
- Perímetro: definido en [`SCOPE.md`](SCOPE.md)
- Inventario completo: [`FILE_MANIFEST.yaml`](FILE_MANIFEST.yaml)

## Regla de completitud

Todo archivo normativo nombrado por la arquitectura debe:

1. Existir en el repositorio.
2. Aparecer en `FILE_MANIFEST.yaml`.
3. Tener propietario y función.
4. Superar `python tools/verify_repository.py`.

## Inicio rápido

```bash
make verify
make test
cp .env.example .env
make local-up
make model-pull
```

Después, abra la consola personal en `http://localhost:3001` o la operacional en `http://localhost:3002`. La guía completa está en [`docs/guides/local-agent-quickstart.md`](docs/guides/local-agent-quickstart.md).

## Navegación

- [`ARCHITECTURE.md`](ARCHITECTURE.md): arquitectura ejecutiva y mapa de componentes.
- [`SCOPE.md`](SCOPE.md): qué está dentro y fuera de esta versión.
- [`COMPLETENESS.md`](COMPLETENESS.md): matriz de cobertura y definición de terminado.
- [`docs/specification/noosfera-2300-arquitectura.md`](docs/specification/noosfera-2300-arquitectura.md): especificación conceptual completa de 2300.
- [`docs/architecture/`](docs/architecture/): vistas técnicas.
- [`docs/architecture/agent-runtime-0.2.md`](docs/architecture/agent-runtime-0.2.md): cableado del agente ejecutable.
- [`registry/`](registry/): fuente de verdad de módulos, servicios, buses y nodos.
- [`schemas/`](schemas/): contratos JSON Schema.
- [`proto/`](proto/): APIs y eventos Protobuf.
- [`policies/`](policies/): constitución y autorización ejecutables.
- [`services/`](services/): dominios desplegables.
- [`adapters/`](adapters/): proveedores externos y dobles seguros de referencia.
- [`packages/`](packages/): bibliotecas compartidas.
- [`apps/`](apps/): consolas personal y operacional.
- [`deploy/`](deploy/): contenedores y Kubernetes.
- [`observability/`](observability/): métricas, trazas, alertas y paneles.
- [`tests/`](tests/): contratos, arquitectura, integración, caos y seguridad.
- [`ops/`](ops/): procedimientos operativos.

## Principio principal

```text
intención → razonamiento → evidencia → autorización → ejecución → auditoría
```

Ningún razonador accede directamente a un actuador. Ningún emisor de permisos genera el plan que autoriza. Ningún ejecutor puede eliminar su propia traza.
