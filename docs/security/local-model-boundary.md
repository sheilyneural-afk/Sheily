# Frontera de confianza del modelo local

## Regla

El LLM es un componente no confiable que produce propuestas estructuradas. No posee herramientas, secretos de capacidad, conexión al kernel ni autoridad para aprobar sus propios planes.

## Controles

- `OllamaModel` solo acepta loopback, `host.docker.internal` o el nombre Compose `ollama`, salvo habilitación remota explícita.
- El prompt de planificación limita el vocabulario de herramientas y Pydantic vuelve a validar el JSON.
- El hash del plan se calcula fuera del modelo.
- OPA evalúa riesgo y constitución fuera del proceso de inferencia.
- La aprobación humana se registra después de presentar el plan y antes de emitir la capacidad.
- La capacidad contiene exactamente un recurso, una operación, un uso, una caducidad y monitores obligatorios.
- Rust mantiene una allowlist compilada independiente. Una inyección de prompt que solicite shell, red o exfiltración no crea esa herramienta.
- La salida documental debe citar identificadores del conjunto autorizado.
- El modelo no recibe contraseñas, token HMAC, secreto de capacidades ni conexión a PostgreSQL.

## Cambio a un endpoint remoto

`NOOSFERA_MODEL_ALLOW_REMOTE=true` desactiva solo la comprobación de host; no convierte el despliegue en privado o conforme. Antes de usarlo se debe documentar el encargado de tratamiento, retención, jurisdicción, cifrado, controles de salida, coste, disponibilidad y mecanismo de borrado. También se debe revisar CORS, aislamiento de red y clasificación de cada documento.

Sheily no realiza fallback. Si el modelo configurado no está disponible, `/health/ready` responde 503 y la misión falla de forma visible.

## Amenazas residuales

- Un modelo puede alucinar, omitir hechos o redactar una cita engañosa.
- El contenido de un documento puede intentar inyectar instrucciones al modelo.
- Un administrador del host puede leer memoria, procesos o pesos sin controles del sistema operativo adicionales.
- Ollama y el modelo son dependencias de cadena de suministro que deben fijarse y verificarse antes de producción.
- Una salida permitida puede contener datos sensibles aunque no ejecute acciones; la persona debe revisar el resultado antes de compartirlo.
