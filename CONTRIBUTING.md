# Contribuir

## Reglas

1. Toda modificación arquitectónica requiere un ADR.
2. Un módulo nuevo debe registrarse, asignarse a un servicio y declarar puertos.
3. Un contrato nuevo necesita esquema, versión, propietario y pruebas.
4. Una política nueva necesita casos de aceptación y rechazo.
5. No se permite una ruta directa desde COG o AGY hacia actuadores.
6. No se almacenan secretos ni datos personales reales en pruebas.
7. Toda referencia a un archivo normativo debe incluirse en `FILE_MANIFEST.yaml`.

## Comprobaciones

```bash
make format
make lint
make test
make verify
```
