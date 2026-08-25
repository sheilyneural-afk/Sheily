# ADR-0009: modelo local por defecto

- Estado: aceptada
- Fecha: 2026-08-25

## Decisión

Sheily 0.2 usa Ollama como proceso local de inferencia y `qwen3:8b` como modelo configurable de referencia. La API HTTP de `experience-service` es una frontera interna entre la consola, la orquestación y el modelo; no implica usar una API de IA en la nube.

El proveedor rechaza hosts remotos salvo que `NOOSFERA_MODEL_ALLOW_REMOTE=true` se configure de forma explícita. No existe conmutación automática a un proveedor externo. El proveedor determinista solo se admite en pruebas y no se presenta como un LLM.

## Motivos

- Los documentos y la conversación pueden permanecer en el nodo de la persona.
- La orquestación no queda acoplada a un modelo concreto ni a su formato privado.
- El kernel Rust puede conservar la autoridad de ejecución aunque cambie el modelo.
- Un fallo de Ollama produce una misión fallida, no una transferencia silenciosa de datos.

## Consecuencias

La calidad y velocidad dependen del hardware y del modelo local. La instalación inicial debe descargar pesos de varios gigabytes. Un operador que habilite un host remoto asume una nueva frontera de confianza y debe acompañarla de una evaluación de privacidad, un ADR y políticas de salida de datos.
