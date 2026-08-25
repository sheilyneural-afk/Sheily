# Esquemas canónicos

JSON Schema 2020-12 es la representación normativa para documentos persistidos e interfaces HTTP. Protobuf es la representación normativa para RPC y eventos binarios.

Reglas:

- No se reutiliza un campo con significado distinto.
- Todo cambio incompatible crea una versión nueva.
- Los campos desconocidos se rechazan en objetos de autorización y ejecución.
- Las marcas temporales expresan intervalos cuando no existe certeza puntual.
- Las referencias a contenido sensible usan hashes y localizadores autorizados.
