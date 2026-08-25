# Descubrimiento de módulos y proveedores runtime

## Problema resuelto

Un catálogo conceptual no demuestra que sus capacidades estén ejecutándose. La aparición de un ID en un YAML solo establece identidad y propiedad; no constituye evidencia de código cargado, salud ni posibilidad de invocación. Tampoco debe existir una cantidad esperada que impida ampliar el sistema.

## Fuentes de verdad

```text
registry/modules/*.yaml
        │ descubre identidad y contrato conceptual
        ▼
services/*/service.yaml
        │ registra proveedores explícitos
        ▼
construcción FastAPI o binario Rust
        │ comprueba ruta + método
        ▼
GET /v1/modules
        │ informa únicamente proveedores cargados
        ▼
prueba de integración/E2E
        │ ejerce comportamiento, políticas y persistencia
        ▼
evidencia verified
```

`registry/modules/index.yaml` contiene un patrón de descubrimiento, no un conteo esperado. `tools/generate_module_maturity.py` calcula el número actual de módulos, proveedores y declaraciones sin implementación. Las pruebas validan unicidad, propiedad, contratos y evidencia, pero no comparan contra una cifra fija.

## Propiedad frente a provisión

El campo `modules` de un servicio significa propiedad conceptual. El campo `providers` describe implementaciones concretas y puede apuntar a un módulo de otro dominio cuando la implementación vertical reside temporalmente en ese proceso. Esto hace visible, por ejemplo, que la memoria personal funcional vive hoy en Experience aunque el dominio propietario siga siendo MEM.

Cada proveedor declara:

- ID estable del proveedor.
- Módulos que materializa.
- Endpoint y métodos HTTP.
- Capacidades concretas.
- Madurez y evidencia comprobable.

En Python, `install_runtime_module_registry` inspecciona las rutas FastAPI ya construidas. Si falta una ruta o método declarado, lanza `RuntimeError` y el servicio no arranca. El ejecutor Rust expone el mismo contrato desde proveedores compilados en el binario.

## Estados

El registro estático usa:

- `declared`: contrato conceptual, sin proveedor registrado.
- `implemented`: proveedor con implementación identificable.
- `integrated`: conectado a su flujo y con prueba de integración.
- `verified`: propiedades críticas verificadas por pruebas específicas.
- `production-ready`: operación, seguridad, SLO y evidencia de producción completos.

El endpoint runtime añade las propiedades `status: loaded`, `route_bound: true` e `invocable: true`. Esas propiedades solo describen cableado vivo; la semántica se demuestra mediante pruebas funcionales y E2E.

## Extensión segura

Para añadir un módulo:

1. Añadir su definición a una familia existente o crear un nuevo archivo que coincida con el patrón de descubrimiento.
2. Asignarle un propietario conceptual.
3. Añadir contratos, buses y políticas necesarios.
4. Si existe implementación, registrar un proveedor con ruta, métodos y evidencia.
5. Ejecutar `make generate`, `make verify`, `make test` y el E2E.

No se modifica ningún número esperado. La incorporación de código sigue siendo explícita: descubrir una definición nueva nunca autoriza ejecutar automáticamente código no confiable.

## Inspección real

Con la pila levantada:

```bash
make runtime-probe
```

La sonda entra por la red privada de Compose, consulta salud y `/v1/modules` de cada proceso, compara la respuesta con su manifiesto y falla si encuentra proveedores ausentes, rutas divergentes o servicios no disponibles. Puede usarse `python tools/probe_runtime_capabilities.py` sin `--via-compose` cuando todos los puertos estén publicados en el host. `tools/run_local_e2e.py` además ejecuta conversación, documentos, consentimiento, memoria, capacidades, Rust, revocación, parada y auditoría; por tanto, no confunde una ruta cargada con una capacidad probada.
