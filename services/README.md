# Servicios

Los módulos lógicos descubiertos se asignan a dominios conceptuales. La cantidad actual se deriva durante la generación y no constituye un límite. Cada directorio contiene:

- `service.yaml`: manifiesto normativo.
- `main.py`: host de referencia ejecutable.
- `README.md`: responsabilidades y prohibiciones.

El host común expone salud, manifiesto y `/v1/modules`. `modules` declara propiedad conceptual; `providers` registra implementaciones concretas. Un proveedor solo se anuncia como cargado si su ruta y método existen en el proceso. Las capacidades futuristas permanecen declaradas y devuelven `501` hasta conectar un proveedor evaluado.
