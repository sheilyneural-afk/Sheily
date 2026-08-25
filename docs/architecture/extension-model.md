# Modelo de extensiones

Un proveedor nuevo se integra mediante un adaptador que declara:

- Identidad y versión.
- Módulos que implementa.
- Tipos de puerto.
- Datos requeridos.
- Buses utilizados.
- Recursos máximos.
- Modos de fallo.
- Pruebas y límites.
- Condición de retirada.

El adaptador empieza sin acceso a memoria duradera, federación o actuadores. La autoridad se amplía por etapas y nunca por autoevaluación.
