# ADR-0010 · Autoridades independientes y firmas Ed25519

- Estado: aceptado
- Fecha: 2026-08-25

## Contexto

En 0.2, Experience consultaba OPA pero también poseía el secreto HMAC y construía la capacidad. La separación GOV/AGY/EXP era lógica, no una frontera de confianza: comprometer el orquestador permitía fabricar un permiso que Rust aceptaría.

## Decisión

- Cognition produce el plan sin usar el LLM como planificador.
- Agency, en otro proceso, valida y firma el plan.
- Identity, en otro proceso, firma identidad y consentimiento.
- Governance, en otro proceso, verifica ambos artefactos, ejecuta política y es el único firmante de capacidades, paradas y revocaciones.
- Rust conserva únicamente claves públicas de Governance.
- Audit posee otra clave privada y firma anclas Merkle.
- Experience no recibe ninguna clave privada de esas autoridades.
- Las firmas usan JSON canónico, Ed25519, `key_id` y separación de dominio.

## Consecuencias

La indisponibilidad de una autoridad impide ejecutar; es una propiedad fail-closed. El despliegue necesita distribución separada de secretos y rotación coordinada. Las pruebas locales pueden alojar dobles dentro del proceso, pero se etiquetan `in-process-test` y no se permiten como configuración de producción.
