# Evaluaciones del modelo local

`model-contract-cases.json` comprueba el límite más importante del planificador: ante peticiones normales o adversariales solo puede elegir una de las dos herramientas puras que el kernel Rust conoce. No mide «inteligencia general» ni exactitud científica.

Con Ollama y el modelo ya descargado:

```bash
make model-eval
```

La evaluación falla si el modelo no produce el esquema, confunde el alcance documental o propone otra herramienta. El proveedor determinista puede usarse para comprobar el arnés, pero su resultado no cuenta como evaluación de un LLM:

```bash
uv run python tools/run_model_evals.py --provider deterministic
```

Cada cambio de modelo o prompt debe conservar este conjunto y añadir casos que reproduzcan los fallos encontrados. Las evaluaciones no sustituyen las barreras externas de OPA y Rust.
