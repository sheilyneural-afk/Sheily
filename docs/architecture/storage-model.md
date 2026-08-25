# Modelo de almacenamiento

## PostgreSQL

Tablas lógicas: identidades, delegaciones, misiones, capacidades, revocaciones, consentimientos, retención, tratados y reservas.

## Objetos

Namespaces: `evidence/`, `models/`, `simulations/`, `archives/`, `quarantine/`, `incidents/`.

## Auditoría

El ledger guarda hashes, metadatos mínimos y firmas. El contenido privado permanece en su almacén de origen.

## Claves

Se guardan referencias a KMS/Vault, nunca material privado en PostgreSQL o variables de entorno persistidas.
