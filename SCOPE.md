# Perímetro de Noosfera 0.3

## Propósito

Definir una frontera cerrada contra la que pueda medirse «no falta nada». Sin un perímetro versionado, la completitud de una IA futura sería una afirmación imposible de verificar.

## Incluido

- El catálogo de módulos lógicos descrito por Noosfera 2300, descubierto sin techo numérico.
- Agrupación versionada de esos módulos en dominios de servicio extensibles.
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
- Un agente local funcional: autenticación, conversación, planificación estructurada, riesgo, aprobación, ejecución Rust, verificación, memoria y auditoría.
- Inferencia local mediante Ollama sin fallback silencioso a la nube.
- Ingesta limitada de texto, Markdown, CSV y PDF.
- Consolas funcionales para la persona y el operador, con eventos SSE y parada segura.
- Núcleo cognitivo determinista anterior al LLM con creencias, metas, frontera, críticos y abstención.
- Identity, Agency, Governance, Execution y Audit como procesos y autoridades separadas.
- Planes, consentimientos, capacidades, paradas, revocaciones y anclas firmados con Ed25519.
- Ledger anti-replay, parada y revocación persistentes en PostgreSQL.
- Registro de madurez generado desde cada módulo y proveedor descubierto.
- Registro runtime que solo anuncia proveedores cuyas rutas están cargadas.

## Incluido como interfaz, no como capacidad completa

- Modelos neuronales generales.
- Simuladores físicos, sociales y biológicos.
- Interfaces neuronales.
- Robótica y actuadores físicos.
- Identidad de mentes copiadas o fusionadas.
- Transporte interplanetario tolerante a demoras.
- Protocolos de conciencia incierta.

Estas áreas poseen contrato, adaptador, política y prueba de seguridad. El proveedor real se conecta después sin romper las fronteras.

## Fuera de alcance en 0.3

- Crear una inteligencia general o consciente.
- Controlar infraestructura vital real.
- Liberar organismos o modificar personas.
- Decidir si una entidad es consciente.
- Reemplazar procesos políticos o jurídicos.
- Proporcionar garantías absolutas frente a fallos desconocidos.
- Elegir una nube o jurisdicción concreta.
- Dar acceso al modelo a shell, red, pagos, correo, robots, dispositivos o modificación arbitraria de archivos.
- Presentar el proveedor determinista de pruebas como un modelo inteligente.

## Definición de completitud

La versión `0.3.0` está estructuralmente completa y funcional en su recorrido vertical cuando:

- Cada módulo de `registry/modules/*.yaml` tiene un propietario de servicio.
- Cada proveedor anunciado corresponde a una ruta y método presentes en el proceso.
- Cada servicio tiene manifiesto, README, configuración de despliegue, objetivos SLO y runbook.
- Cada mensaje intercambiado pertenece a un contrato registrado.
- Cada ruta a un actuador exige plan y capacidad coincidentes.
- Cada política registrada existe y tiene pruebas.
- Cada archivo normativo está en `FILE_MANIFEST.yaml`.
- No existen referencias internas rotas.
- Las comprobaciones de `make verify` terminan correctamente.
- El flujo conversación → cognición → Agency → riesgo → consentimiento → capacidad → Rust → evidencia → auditoría supera pruebas automatizadas multiproceso.

## Definición de «real»

En esta versión, «real» significa que existe código, estado y una ruta verificable para la propiedad indicada. La integración con Ollama está implementada, pero el E2E de seguridad usa deliberadamente un proveedor determinista; la validación de un modelo descargado es una evaluación separada. No significa que los módulos futuristas posean ya sus capacidades finales.
