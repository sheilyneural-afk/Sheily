# Perímetro de Noosfera 0.1

## Propósito

Definir una frontera cerrada contra la que pueda medirse «no falta nada». Sin un perímetro versionado, la completitud de una IA futura sería una afirmación imposible de verificar.

## Incluido

- Los 105 módulos lógicos descritos por Noosfera 2300.
- Agrupación de esos módulos en 14 dominios de servicio.
- Contratos canónicos para intención, evidencia, capacidad, auditoría, identidad, memoria, misión, riesgo, recursos, federación y actualización.
- Políticas ejecutables para derechos mínimos, autorización, privacidad, riesgo, emergencia y evolución.
- Rutas de datos, intención, evidencia, autorización, acción y auditoría.
- Una pasarela de ejecución incapaz de aceptar lenguaje natural.
- Registro de módulos, servicios, nodos, buses, datos, riesgos y propietarios.
- Despliegue local y plantilla de despliegue Kubernetes.
- Observabilidad, respuesta a incidentes, continuidad, recuperación y copias.
- Verificación automática de archivos, referencias y registros.
- Consolas de referencia para un sujeto y un operador.
- Pruebas de arquitectura, contrato, política, integración, seguridad, caos y recuperación.

## Incluido como interfaz, no como capacidad completa

- Modelos neuronales generales.
- Simuladores físicos, sociales y biológicos.
- Interfaces neuronales.
- Robótica y actuadores físicos.
- Identidad de mentes copiadas o fusionadas.
- Transporte interplanetario tolerante a demoras.
- Protocolos de conciencia incierta.

Estas áreas poseen contrato, adaptador, política y prueba de seguridad. El proveedor real se conecta después sin romper las fronteras.

## Fuera de alcance en 0.1

- Crear una inteligencia general o consciente.
- Controlar infraestructura vital real.
- Liberar organismos o modificar personas.
- Decidir si una entidad es consciente.
- Reemplazar procesos políticos o jurídicos.
- Proporcionar garantías absolutas frente a fallos desconocidos.
- Elegir una nube o jurisdicción concreta.

## Definición de completitud

La versión `0.1.0` está estructuralmente completa cuando:

- Cada módulo de `registry/modules/*.yaml` tiene un propietario de servicio.
- Cada servicio tiene manifiesto, README, configuración de despliegue, objetivos SLO y runbook.
- Cada mensaje intercambiado pertenece a un contrato registrado.
- Cada ruta a un actuador exige plan y capacidad coincidentes.
- Cada política registrada existe y tiene pruebas.
- Cada archivo normativo está en `FILE_MANIFEST.yaml`.
- No existen referencias internas rotas.
- Las comprobaciones de `make verify` terminan correctamente.

## Definición de «real»

En esta versión, «real» significa que la arquitectura puede desplegarse como plano de control, validar contratos, evaluar políticas, emitir capacidades de prueba, registrar decisiones y rechazar rutas prohibidas. No significa que los módulos científicos futuristas posean ya sus capacidades finales.
