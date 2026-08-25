# Persistencia relacional

Las migraciones son monotónicas. No contienen datos reales. Cada dominio usa un rol de base de datos distinto; que las tablas compartan clúster no implica acceso cruzado.

La auditoría crítica requiere además un backend append-only independiente.
