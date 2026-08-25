# Noosfera

Repositorio de referencia para convertir la arquitectura conceptual **Noosfera 2300** en un sistema construible, verificable y evolutivo.

Este repositorio no afirma implementar una superinteligencia ni tecnología inexistente. Implementa el **esqueleto real del sistema**: límites de confianza, contratos, módulos lógicos, servicios, políticas, topología, observabilidad, pruebas y mecanismos de completitud.

## Estado

- Versión de arquitectura: `0.1.0`
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
make local-up
```

## Navegación

- [`ARCHITECTURE.md`](ARCHITECTURE.md): arquitectura ejecutiva y mapa de componentes.
- [`SCOPE.md`](SCOPE.md): qué está dentro y fuera de esta versión.
- [`COMPLETENESS.md`](COMPLETENESS.md): matriz de cobertura y definición de terminado.
- [`docs/specification/noosfera-2300-arquitectura.md`](docs/specification/noosfera-2300-arquitectura.md): especificación conceptual completa de 2300.
- [`docs/architecture/`](docs/architecture/): vistas técnicas.
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
