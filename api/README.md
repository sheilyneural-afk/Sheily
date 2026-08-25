# Interfaces públicas

`openapi.yaml` describe solicitudes síncronas. `asyncapi.yaml` describe los buses. Las interfaces administrativas y los actuadores usan redes e identidades separadas.

Desde 0.3, OpenAPI se regenera con `python tools/generate_openapi.py` e incluye consentimiento, revocación, parada y los artefactos cognitivos/criptográficos de cada misión. AsyncAPI registra los circuitos de misión, parada y revocación. FastAPI publica además `/docs`.
