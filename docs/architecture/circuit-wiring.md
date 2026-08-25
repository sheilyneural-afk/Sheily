# Cableado de circuitos

## Regla

Un bus define privilegio y semántica. Que dos servicios compartan NATS no significa que compartan permisos; identidades, temas, políticas de red y consumidores limitan cada circuito.

## Unión crítica

```text
AGY --plan/hash----┐
                   ├─ EXE-01 → comando determinista
GOV --capability---┘
```

La unión requiere coincidencia exacta de hash. Los datos de COG nunca llegan a `BUS-ACT`.

## Separaciones obligatorias

- `BUS-AUT` y `BUS-STP` usan identidades y cuotas propias.
- `BUS-AUD` es de solo adición desde operación.
- `BUS-FED` termina en cuarentena.
- `BUS-EVO` no monta volúmenes de producción en escritura.
- `BUS-ACT` no admite lenguaje natural ni esquemas abiertos.

## ACL

Las ACL se generan desde `registry/modules/*.yaml`, `registry/services.yaml` y `registry/buses.yaml`. Un publicador no registrado se rechaza aunque posea conectividad de red.
