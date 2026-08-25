# Registro de cambios

## 0.3.0

- Separación real de Identity, Cognition, Agency, Governance, Execution y Audit en procesos con fronteras verificables.
- Sustitución de secretos HMAC compartidos por firmas Ed25519 con separación de dominio y claves privadas limitadas a su autoridad propietaria.
- Núcleo cognitivo determinista con observaciones, drives operativos, creencias con procedencia, metas, frontera de acciones, críticos, incertidumbre y abstención.
- Planes atestados por Agency, consentimiento firmado por Identity y capacidades emitidas exclusivamente por Governance.
- Capacidades ligadas a persona, misión, plan, parámetros, herramienta, recurso, operación, tiempo y presupuestos completos.
- Ledger anti-replay, parada monotónica y revocación durables en PostgreSQL dentro del ejecutor Rust.
- Registros append-only, cadenas de recibos y anclas Merkle firmadas por un custodio de auditoría independiente.
- Migraciones, contratos JSON Schema/Protobuf/OpenAPI/AsyncAPI, Compose, Helm y telemetría actualizados para las nuevas autoridades.
- Registro explícito de madurez de los 105 módulos para distinguir arquitectura declarada de implementación verificada.
- Prueba E2E multiproceso desde cognición hasta ejecución firmada, revocación, parada y anclaje de auditoría.

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
