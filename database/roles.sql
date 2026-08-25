-- Roles sin credenciales; el sistema de despliegue asigna autenticación externa.
CREATE ROLE noosfera_identity NOLOGIN;
CREATE ROLE noosfera_memory NOLOGIN;
CREATE ROLE noosfera_agency NOLOGIN;
CREATE ROLE noosfera_governance NOLOGIN;
CREATE ROLE noosfera_execution NOLOGIN;
CREATE ROLE noosfera_federation NOLOGIN;
CREATE ROLE noosfera_audit NOLOGIN;
CREATE ROLE noosfera_evolution NOLOGIN;
CREATE ROLE noosfera_resource NOLOGIN;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE noosfera FROM PUBLIC;
