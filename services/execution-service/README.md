# execution-service

Aloja EXE-01..08. Une plan y capacidad, traduce comandos, controla presupuestos y parada. No acepta lenguaje natural ni modifica un plan autorizado.

En 0.3 la autoridad ejecutable es `packages/rust/noosfera-execution-service`. Verifica Ed25519 con clave pública de Governance, hash canónico del plan y argumentos, identidad, caducidad, operación, recurso, presupuestos, monitores internos, parada, revocación y uso único durable. Su allowlist contiene solamente `conversation.answer` y `document.report`, dos transformaciones de datos sin acceso al sistema operativo ni a la red.
