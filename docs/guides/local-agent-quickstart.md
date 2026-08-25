# Ejecutar Sheily 0.3 en local

## Requisitos

- Docker con Compose v2.
- Al menos 12 GB de RAM; una GPU compatible acelera Ollama, pero no es obligatoria.
- `curl`, Bash y espacio suficiente para el modelo configurado.

## Inicio

```bash
cp .env.example .env
```

Cambie como mínimo `NOOSFERA_LOCAL_PASSWORD` y `NOOSFERA_INTERNAL_SERVICE_TOKEN`. Para un entorno que no sea de desarrollo genere cuatro pares Ed25519 distintos para Identity, Agency, Governance y Audit. Las claves privadas se inyectan únicamente en su servicio propietario; Experience y Rust reciben solo claves públicas.

```bash
make local-up
make model-pull
```

Servicios de uso humano:

- API y OpenAPI interactiva: `http://localhost:8101/docs`
- Consola personal: `http://localhost:3001`
- Consola operacional: `http://localhost:3002`
- Ollama: `http://localhost:11434`

El usuario inicial es el valor de `NOOSFERA_LOCAL_USERNAME`, por defecto `sheily`. No use los secretos de ejemplo fuera de una máquina de desarrollo.

## Primer recorrido

1. Entre en la consola personal.
2. Añada uno o varios archivos `.txt`, `.md`, `.csv` o `.pdf`.
3. Escriba «Analiza estos documentos y crea un informe».
4. Revise objetivo, pasos, riesgo y motivos.
5. Autorice una sola vez o rechace.
6. Observe la línea temporal y las fuentes del resultado.
7. Si habilitó memoria, compruebe o borre el recuerdo en el panel lateral.
8. Abra la consola operacional para consultar recibos o activar la parada segura.

## Verificación sin descargar un modelo

El proveedor determinista existe únicamente para pruebas automatizadas:

```bash
uv sync --extra dev
uv run pytest -q
cargo test --workspace
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build
```

No configure `deterministic` como si fuera un LLM real. El modo de producción lo rechaza.

## Parada y limpieza

La parada segura se activa desde la consola operacional y bloquea nuevas ejecuciones tanto en PostgreSQL como en Rust. Para detener los contenedores sin borrar datos:

```bash
make local-down
```

Compose conserva los volúmenes de PostgreSQL, NATS, MinIO y Ollama. Borrarlos es una operación separada y destructiva que el proyecto no automatiza.

## E2E sin descargar Ollama

```bash
make local-e2e
```

Esta prueba usa procesos reales para Identity, Cognition, Agency, Governance, OPA, PostgreSQL, NATS, Rust, Audit y Experience. El ejecutor de prueba entra por la red privada de Compose, por lo que las autoridades no necesitan exponer sus APIs al host. El único doble es la generación lingüística determinista, identificada expresamente como prueba.
