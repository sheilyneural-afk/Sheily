# Despliegue

- `local/`: entorno reproducible sin actuadores reales.
- `images/`: imagen de referencia común.
- `services/`: parámetros explícitos por servicio.
- `helm/noosfera/`: despliegue Kubernetes.

El entorno local es solo de desarrollo. Las claves de ejemplo no son válidas para producción.

Compose 0.2 incluye PostgreSQL, NATS, OPA, observabilidad, Ollama, el servicio Rust, los catorce dominios y las dos consolas. El modelo se descarga de forma separada con `make model-pull`, que concede salida temporal únicamente al contenedor de Ollama y la retira al terminar.
