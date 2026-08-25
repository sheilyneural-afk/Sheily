# Seguridad

## Notificación

Los incidentes deben registrarse de forma privada con el propietario definido en `registry/ownership.yaml`. No se incluyen secretos ni datos de afectados en canales públicos.

## Suposición de compromiso

La arquitectura asume que cualquier modelo, operador o servicio individual puede fallar. Las acciones de alto impacto requieren separación de funciones, capacidades de alcance mínimo, testigos diversos y parada independiente.

## Prohibiciones

- Credenciales en el repositorio.
- Capacidades universales o sin caducidad.
- Lenguaje natural en `BUS-ACT`.
- Ejecución de modelos externos fuera de cuarentena.
- Auditoría con acceso indiscriminado a memoria privada.
- Desactivar políticas por una variable de entorno en producción.

## Modelo de amenazas

Véase `docs/security/threat-model.md` y `docs/security/trust-boundaries.md`.
