# Gestión de claves

- Identidad, firma de capacidades, auditoría y despliegue usan jerarquías separadas.
- No existe clave maestra universal.
- Las claves críticas requieren testigos o umbral multipartito.
- Toda rotación conserva la cadena histórica.
- La revocación tiene rutas independientes y prioridad.
- Las claves de desarrollo nunca firman artefactos de producción.
- Las copias se cifran con custodios y procedimientos de recuperación ensayados.

## Distribución 0.3

| Servicio | Material privado | Material público |
|---|---|---|
| Identity | `IDENTITY_PRIVATE_KEY_B64` | ninguno necesario |
| Agency | `AGENCY_PRIVATE_KEY_B64` | ninguno necesario |
| Governance | `GOVERNANCE_PRIVATE_KEY_B64` | Identity y Agency |
| Execution | ninguno | Governance |
| Audit | `AUDIT_PRIVATE_KEY_B64` | ninguno necesario |
| Experience | ninguno de autoridad | Identity, para verificar tokens |

El Compose de referencia no usa `env_file` dentro de los contenedores: enumera explícitamente las variables, de modo que una clave privada de Governance no se filtre accidentalmente a Experience.

## Rotación

1. Genere el nuevo par fuera del repositorio.
2. Registre un `key_id` nuevo y conserve la clave pública anterior durante la ventana de validez de artefactos ya emitidos.
3. Actualice primero los verificadores.
4. Cambie después el firmante.
5. Espere a que caduquen tokens, attestations y capacidades anteriores.
6. Retire la clave pública antigua y emita un ancla de auditoría.

La implementación de referencia configura un firmante activo por autoridad. Una rotación sin reinicio exige ampliar el verificador a un keyring; hasta entonces la rotación es coordinada y debe realizarse con safe-stop activo.
