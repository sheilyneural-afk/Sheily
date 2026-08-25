# Persistencia relacional

Las migraciones son monotónicas. No contienen datos reales. Cada dominio usa un rol de base de datos distinto; que las tablas compartan clúster no implica acceso cruzado.

`0008_authority_boundaries.sql` añade los ciclos cognitivos, concesiones de gobierno,
ledger anti-replay, parada y revocaciones. `0009_immutable_audit.sql` añade anclas
Merkle y bloquea la modificación o el borrado de las tablas probatorias.

La auditoría crítica requiere además exportar periódicamente las anclas firmadas a
un backend WORM independiente del clúster operacional.
