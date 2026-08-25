# Registro canónico

Esta carpeta es la fuente de verdad del inventario arquitectónico.

- `modules/index.yaml`: regla de descubrimiento extensible, sin cantidad esperada fija.
- `services.yaml`: dominios desplegables.
- `buses.yaml`: circuitos y garantías.
- `topics.yaml`: temas de eventos.
- `nodes.yaml`: tipos de nodo soberano.
- `contracts.yaml`: esquemas y propietarios.
- `policies.yaml`: políticas ejecutables.
- `data-classes.yaml`: clasificación de información.
- `risk-classes.yaml`: niveles de riesgo.
- `actuator-classes.yaml`: clases de actuador.
- `ownership.yaml`: responsables y revisores.
- `module-maturity.yaml`: conteos, proveedores y madurez derivados del inventario actual.

Los identificadores son estables. Los nombres pueden evolucionar mediante un cambio versionado. Añadir un archivo de familia o un módulo no requiere cambiar un techo numérico; sí exige identidad única, propietario, contrato y, para poder ejecutarlo, un proveedor explícito.
