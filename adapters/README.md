# Adaptadores

Los adaptadores conectan contratos Noosfera con tecnología externa. Un adaptador no obtiene más autoridad que el módulo que lo invoca.

`reference/` contiene dobles seguros para desarrollo:

- Modelo determinista sin red.
- Actuador nulo que nunca cambia el mundo.
- Política que deniega por defecto.
- Ledger en memoria para pruebas.
- Almacén en memoria.
- Reloj inyectable.

Un proveedor real debe añadir manifiesto, amenaza, SLO, runbook y pruebas adversariales.
