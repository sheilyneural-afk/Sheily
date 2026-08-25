# Arquitectura ejecutable de Sheily 0.3

## Propósito y alcance

Sheily 0.3 es un agente local gobernado con un núcleo cognitivo explícito y cuatro fronteras criptográficas independientes. No es una AGI, no declara conciencia y no implementa literalmente la tecnología especulativa de Noosfera 2300. Implementa el subconjunto que puede verificarse hoy: conversación, documentos, deliberación acotada, consentimiento, políticas, capacidades, ejecución pura, memoria, revocación, parada y auditoría.

El principio de diseño es:

```text
el LLM realiza lenguaje
        ≠
el núcleo cognitivo selecciona un plan
        ≠
Agency atesta ese plan
        ≠
Governance concede autoridad
        ≠
Rust ejecuta una allowlist
```

## Cableado completo

```text
Persona
  │ credencial
  ▼
Identity Service ──firma──► token / approval receipt
  │                              │
  │ clave pública                │ consentimiento(user, mission, plan_hash)
  ▼                              ▼
Experience Service ───────► Cognition Service
  │                         │ observación, drives, creencias, metas,
  │                         │ frontera, críticos, incertidumbre, plan
  │                         ▼
  ├──────────────────────► Agency Service
  │                         │ valida plan, alcance y presupuesto
  │                         └──firma──► PlanAttestation
  │                                      │
  ├──────────────────────────────────────► Governance Service
  │                                      │ verifica Agency + Identity
  │                                      │ ejecuta OPA
  │                                      └──firma──► CapabilityGrant
  │                                                     │
  │ documentos → bloques versionados → contexto crítico │
  │ LLM local produce ModelDraft sin autoridad          │
  ├──────────────────────► Audit Service                 │
  │                         │ valida hash, unión, cita exacta,
  │                         │ soporte, límites y cobertura
  │                         └──firma──► ModelOutput + EvidenceBundle
  │ resultado sellado; su hash queda ligado ────────────┘
  ▼
Execution Service (Rust)
  │ verifica Ed25519, plan, argumentos, identidades, tiempo,
  │ presupuestos, revocación, safe-stop, allowlist y uso único
  │ consume la capacidad en PostgreSQL antes de responder
  ▼
Experience verifica firma de Audit y persiste resultado
  │
  ├──► memoria consentida
  ├──► eventos encadenados
  └──► Audit Service ──firma──► raíz Merkle periódica
```

## Secuencia normal

1. Identity autentica localmente y firma un token Ed25519 de corta duración.
2. Experience verifica el token solamente con la clave pública de Identity.
3. Experience crea una misión y un evento append-only.
4. Cognition crea un `CognitiveCycle` sin consultar al LLM para decidir el plan.
5. El ciclo explicita observación, necesidades operativas, creencias con procedencia, metas, alternativas, críticos, incertidumbre y abstención.
6. Agency comprueba la relación exacta entre herramienta, operación, recurso, documentos y límites.
7. Agency firma un `PlanAttestation` ligado a misión, persona, prompt, contexto, plan y presupuesto.
8. Governance verifica la firma de Agency y evalúa riesgo y constitución mediante OPA.
9. Si la política lo exige, Identity firma un `ApprovalReceipt` ligado a `user_id + mission_id + plan_hash`.
10. Experience extrae una versión inmutable y bloques con página, sección, posición y hash; prioriza bloques críticos y relevancia dentro del presupuesto.
11. El LLM local propone afirmaciones y selecciona alias efímeros de fuente/bloque (`S1/B7`); no recibe autoridad para fijar el texto literal, crear sellos ni declarar estados de verificación.
12. Experience resuelve cada alias contra el contexto inmutable y extrae el bloque exacto. Audit comprueba hashes, versión, unión bloque-documento, cita literal, soporte léxico, cobertura y omisiones críticas; descarta afirmaciones sin apoyo, conserva objeciones y firma el informe.
13. Experience verifica la firma pública de Audit y calcula el hash canónico del `ModelOutput` ya sellado.
14. Governance vuelve a evaluar el plan, verifica el consentimiento y emite una capacidad para ese plan y ese resultado exactos.
15. Rust verifica las firmas públicas de Governance y Audit, todas las vinculaciones y los hashes del paquete probatorio.
16. Rust consulta parada y revocación, valida la herramienta pura, consume la capacidad una vez y devuelve un recibo del kernel.
17. Experience vuelve a validar el resultado y la regla epistemológica de estado interno.
18. El resultado y, si fue autorizado, la memoria se guardan; toda fase emite duración y recibo.

## Artefactos criptográficos

| Artefacto | Firmante único | Verificadores | Vinculación mínima |
|---|---|---|---|
| Token de acceso | Identity | Experience, Identity | identidad, rol, emisión, expiración, nonce |
| ApprovalReceipt | Identity | Governance | persona, misión, plan, memoria, decisión, expiración |
| PlanAttestation | Agency | Governance | persona, misión, prompt, contexto, plan, presupuesto |
| CapabilityGrant | Governance | Rust | persona, misión, plan, argumentos, operación, recurso, límites, tiempo |
| StopDirective | Governance | Rust | estado, razón, versión monotónica, operador |
| RevocationDirective | Governance | Rust | capacidad, razón, versión, operador |
| AuditAnchor | Audit | verificadores externos | primer/último evento, cantidad, raíz Merkle |
| DocumentVerificationReport | Audit | Experience, Rust | paquete de evidencia, afirmaciones aceptadas/rechazadas, método, objeciones, tiempo |

Las firmas usan Ed25519 y separación de dominio. Un byte nulo separa el identificador de protocolo del JSON canónico para impedir reutilizar una firma en otro tipo de artefacto.

## Propiedad A=B=C=D

Rust no confía en un único hash enviado por Experience:

```text
A = capability.plan_hash
B = request.plan_hash
C = sha256(canonical(request.plan))
D = attested plan_hash verificado previamente por Governance

A == B == C == D
```

Los argumentos tienen una unión independiente:

```text
capability.arguments_hash
        ==
sha256(canonical(request.parameters))
```

Así, autorizar el plan A no permite ejecutar el plan B, y autorizar el resultado X no permite sustituirlo por Y después de la firma.

## Persistencia por autoridad

| Tabla | Autoridad | Semántica |
|---|---|---|
| `agent_missions` | Experience | estado durable de misión |
| `agent_documents` | Experience | versión, hashes y extractor de cada fuente autorizada |
| `agent_document_blocks` | Experience | bloques direccionables con página, sección, offsets e integridad |
| `agent_events` | Experience/Audit | eventos encadenados append-only |
| `cognitive_cycles` | Cognition | episodios cognitivos completos |
| `cognitive_beliefs` | Cognition | memoria semántica con procedencia y revisión temporal |
| `governance_grants` | Governance | emisión idempotente; un consentimiento no crea permisos ilimitados |
| `governance_control` | Governance | secuencias monotónicas de parada y revocación |
| `execution_capability_ledger` | Rust | consumo atómico y protección anti-replay compartida |
| `execution_control` | Rust | parada durable y visible para todas las réplicas |
| `execution_revocations` | Rust | revocaciones durables antes del uso |
| `audit_anchors` | Audit | raíces Merkle firmadas append-only |
| `audit_document_verifications` | Audit | informes y paquetes probatorios firmados append-only |

Las migraciones `0008_authority_boundaries.sql`, `0009_immutable_audit.sql` y `0010_document_intelligence.sql` crean estas estructuras y bloquean `UPDATE`/`DELETE` sobre los registros probatorios.

## Inteligencia documental verificable

Qwen es el órgano de lenguaje, no el sistema de verdad. Para documentos, el recorrido real es:

```text
bytes autorizados
  → content_hash + version_id
  → extracción estructural (página, sección, tipo, offsets)
  → bloques con text_hash y origen «contenido comunicado»
  → selección reproducible critical-first + relevancia léxica
  → borrador lingüístico {afirmaciones, alias de evidencia, contradicciones,
                          límites, desconocidos}
  → resolución determinista alias → bloque exacto fuera del LLM
  → ModelDraft con citas derivadas de los bloques inmutables
  → Audit descarta soporte inválido e incorpora límites críticos omitidos
  → EvidenceBundle {fuentes, transformaciones, supuestos, contraevidencia,
                    objeciones, condiciones de invalidación, cobertura}
  → DocumentVerificationReport firmado
  → Governance liga el resultado exacto a una capacidad de un uso
  → Rust recalcula hashes y verifica la firma de Audit
```

La salida diferencia contenido comunicado por la fuente, inferencia e hipótesis. Una cita tiene `document_id`, `version_id`, `block_id`, fragmento literal, página, ruta de sección y relación. La consola enseña las afirmaciones aceptadas, límites detectados por el sistema, artefactos mencionados pero no adjuntos, cobertura, citas desplegables, hashes, firmante y objeciones abiertas.

`passed-with-open-objections` no significa «verdad demostrada». Significa que integridad, procedencia, coincidencia literal y soporte léxico superaron el método declarado. La implicación semántica completa sigue siendo una objeción explícita hasta disponer de verificadores más fuertes o revisión humana.

## Núcleo cognitivo

El núcleo implementado es deliberadamente pequeño y causalmente observable:

```text
petición autorizada
  → observación normalizada
  → drives operativos
  → creencias con procedencia
  → metas de usuario/constitucionales/homeostáticas
  → frontera {responder, informar documentos, abstenerse}
  → críticos de seguridad, privacidad y evidencia
  → selección
  → MissionPlan
```

No crea mandatos autónomos. Toda meta productiva nace de una petición autenticada; las metas internas solamente limitan seguridad, privacidad, evidencia y recursos.

La memoria cognitiva se separa en:

- Trabajo: el `CognitiveCycle` actual.
- Episódica: ciclos persistidos por misión.
- Semántica: creencias consolidadas por persona y hash de proposición.
- Procedimental: algoritmos versionados del kernel, no texto autoeditable.
- Personal: resultados almacenados solo tras política y consentimiento firmado.

## Regla epistemológica para estado interno

El runtime no proporciona al modelo evidencia afectiva, consciente o subjetiva. El contrato de salida incluye `internal_state_claims`; cualquier elemento no vacío se rechaza con `sealed_affective_unobserved_state_not_realized`.

La evolución futura puede permitir una afirmación interna únicamente si existe un artefacto con:

```text
observed = true
+ value
+ confidence
+ provenance
+ freshness
+ sealed = true
```

No se debe relajar este control para convertir una ausencia de observación en una frase plausible.

## Presupuestos

La capacidad transporta límites de tiempo de pared, CPU, memoria, entrada, salida, tokens, coste, llamadas, procesos hijos y red. En el runtime de referencia:

- Rust impone tamaño de entrada/salida, tiempo de su propia ejecución, llamada única, cero procesos hijos y red prohibida.
- Ollama recibe los límites de contexto y generación.
- Los clientes HTTP tienen tiempos máximos.
- CPU y memoria se expresan y validan, pero el ejecutor actual solo realiza transformaciones puras dentro de su propio proceso; un futuro proveedor de procesos deberá imponerlos además mediante cgroups/seccomp.

## Fallos fail-closed

La misión falla o se detiene si ocurre cualquiera de estas condiciones:

- Identity, Cognition, Agency, Governance, OPA, PostgreSQL o Rust no están disponibles.
- La firma, el `key_id`, la expiración o el dominio criptográfico no coinciden.
- Cambian plan, identidad, argumentos, herramienta, operación o recurso.
- Falta consentimiento o no permite memoria.
- La capacidad fue usada o revocada.
- La parada está activa o el ledger no puede consultarse.
- Falta una cita exacta, cambia su bloque o versión, aparece una fuente no autorizada o ninguna afirmación supera la verificación.
- El paquete de evidencia o el informe no coincide con sus hashes o con la firma de Audit.
- El modelo intenta declarar estado interno no observado.
- Se supera un límite.

No existe fallback silencioso a nube, HMAC compartido ni autorización local dentro de Experience.

## Pruebas

- Python prueba flujo de API, cognición, firmas, alteraciones, consentimiento, memoria, parada y auditoría.
- Rust prueba hash del plan, firmas de Governance/Audit, argumentos, paquete documental, uso único, parada y revocación.
- `governed-e2e` levanta PostgreSQL, NATS, OPA, Identity, Cognition, Agency, Governance, Rust, Audit y Experience en procesos separados.
- El E2E de CI usa el proveedor determinista para que la seguridad no dependa de descargar un modelo. `make local-e2e-ollama` repite el mismo recorrido con el modelo local real, y `make model-eval` comprueba los contratos estructurados y casos adversariales del adaptador.

## Límite honesto de completitud

El catálogo conceptual actual se descubre desde `registry/modules/*.yaml`; su tamaño presente no es una constante ni un máximo. `registry/module-maturity.yaml` deriva los estados `declared`, `implemented`, `integrated`, `verified` y `production-ready` desde proveedores explícitos. El endpoint runtime `/v1/modules` es la fuente autoritativa para saber qué rutas están cargadas e invocables. Un servicio arrancable no convierte automáticamente sus declaraciones en capacidades reales.
