# experience-service

Aloja EXP-01..06 y constituye el backend funcional de Sheily 0.2. Expone autenticación local, conversaciones, documentos, misiones, aprobación, memoria, auditoría y streaming SSE. Orquesta el modelo local, OPA, NATS, PostgreSQL y la autoridad Rust sin dar al modelo acceso directo a ninguno de ellos.

No decide políticas ni ejecuta actuadores. Emite el sobre de capacidad solo después de la decisión de gobierno y delega su verificación al kernel Rust. La memoria se escribe únicamente tras consentimiento explícito y autorización OPA.
