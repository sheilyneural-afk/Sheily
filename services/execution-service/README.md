# execution-service

Aloja EXE-01..08. Une plan y capacidad, traduce comandos, controla presupuestos y parada. No acepta lenguaje natural ni modifica un plan autorizado.

En 0.2 la autoridad ejecutable es `packages/rust/noosfera-execution-service`. Verifica firma HMAC, hash canónico del plan, caducidad, operación, recurso, monitores, parada y uso único. Su allowlist contiene solamente `conversation.answer` y `document.report`, dos transformaciones de datos sin acceso al sistema operativo ni a la red.
