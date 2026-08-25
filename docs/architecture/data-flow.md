# Flujo de datos

## Ingesta

1. PER recibe una observación firmada.
2. PER-02 valida sensor y calibración.
3. PER-03 asigna estado epistemológico.
4. MEM-05 enlaza procedencia.
5. Solo una vista autorizada llega a COG.

## Derivación

Cada transformación produce un nuevo hash y mantiene referencias a progenitores. Una inferencia nunca sustituye el registro observado.

## Persistencia

- Metadatos transaccionales en PostgreSQL.
- Contenido grande cifrado en objetos.
- Eventos en JetStream con retención por circuito.
- Auditoría en ledger append-only.

## Eliminación

MEM-06 elimina contenido y derivados razonablemente localizables; conserva únicamente una prueba no reconstructiva cuando la ley o la auditoría lo exigen.
