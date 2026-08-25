# Despliegue

- `local/`: entorno reproducible sin actuadores reales.
- `images/`: imagen de referencia común.
- `services/`: parámetros explícitos por servicio.
- `helm/noosfera/`: despliegue Kubernetes.

El entorno local es solo de desarrollo. Las claves de ejemplo no son válidas para producción.

Compose 0.3 incluye PostgreSQL, NATS, OPA, observabilidad, Ollama, autoridades Identity/Agency/Governance/Audit independientes, el servicio Rust, los catorce dominios y las dos consolas. Las claves privadas solo llegan a su autoridad. El modelo se descarga de forma separada con `make model-pull`.
