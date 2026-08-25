# Topología de despliegue

## Nodo mínimo

```text
zona de interacción: EXP
zona privada: IDN + MEM
zona cognitiva: PER + COG + AGY
zona constitucional: GOV + TMP + RES
zona de ejecución: EXE + interbloqueos
zona de seguridad: SEC
zona de auditoría: AUD
zona de evolución aislada: EVO
zona de frontera: FED
```

## Reglas

- GOV, EXE, SEC, AUD y TMP usan cuentas y dominios de fallo diferentes.
- AUD no comparte credenciales administrativas con EXE.
- COG no posee ruta de red a actuadores.
- FED no entra directamente en MEM, GOV o EXE.
- Los controladores vitales pueden operar sin el clúster.

## Regiones

Cada región tiene autoridad local. La federación intercambia paquetes, no extiende un plano de control síncrono entre planetas.
