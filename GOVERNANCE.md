# Gobernanza del repositorio

## Autoridades separadas

- Arquitectura: aprueba límites y ADR.
- Seguridad: aprueba fronteras y excepciones.
- Contratos: aprueba cambios incompatibles.
- Constitución: aprueba políticas de derechos.
- Operación: despliega versiones ya aprobadas.

Ningún rol aprueba por sí solo una modificación que simultáneamente amplíe capacidad, autoridad y acceso a datos.

## Versionado

- Cambios compatibles: versión menor.
- Cambios incompatibles de contrato o derecho: versión mayor.
- Correcciones sin cambio semántico: parche.

## Excepciones

Toda excepción tiene propietario, razón, alcance, fecha de caducidad y prueba de retirada. No existen excepciones permanentes implícitas.
