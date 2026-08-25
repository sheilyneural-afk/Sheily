# Registro de cambios

## 0.2.0

- Incorporación de Sheily como agente local-first funcional sobre el plano de control.
- Proveedor Ollama con salida estructurada, límites de contexto y ausencia de fallback silencioso.
- API de autenticación, conversación, documentos, misiones, aprobación, memoria, auditoría y parada.
- Persistencia PostgreSQL para el runtime y eventos de misión encadenados publicados en NATS.
- Gobierno OPA para riesgo, constitución y escritura de memoria.
- Servicio Rust que verifica firma, hash de plan, capacidad, monitores, uso, límites y allowlist.
- Consolas personal y operacional conectadas al backend y empaquetadas para Compose.
- Contratos JSON Schema, Protobuf, OpenAPI y AsyncAPI del flujo del agente.
- Pruebas del recorrido documental, límites de modelo local, autenticación y parada segura.

## 0.1.0

- Creación del perímetro implementable.
- Registro de 105 módulos y 14 dominios.
- Definición de contratos, buses, políticas y servicios.
- Inclusión de despliegue, observabilidad, seguridad y pruebas.
- Incorporación de un verificador de completitud del repositorio.
