# Federación tolerante a demoras

Cada paquete incluye origen, destino, protocolo, creación, caducidad, hash, límite de saltos y firma.

El receptor:

1. Valida estructura e integridad.
2. Rechaza repetición y caducidad.
3. Negocia versión.
4. Abre contenido en cuarentena.
5. Traduce constituciones.
6. Toma una decisión local.

No se usa consenso global para control vital. Las bifurcaciones legítimas se conservan hasta una reconciliación explícita.
