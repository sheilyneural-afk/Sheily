# Mapa de dominios

Los 14 dominios son fronteras de propiedad, no una obligación de desplegar 14 máquinas.

```mermaid
flowchart TB
  subgraph subject[Plano del sujeto]
    EXP --> IDN
    EXP --> MEM
  end
  subgraph cognition[Plano cognitivo]
    PER --> COG
    COG --> AGY
    MEM --> COG
  end
  subgraph authority[Plano de autoridad]
    AGY --> GOV
    IDN --> GOV
    TMP --> GOV
    RES --> GOV
  end
  subgraph action[Plano de acción]
    GOV --> EXE
    AGY --> EXE
    EXE --> PER
  end
  FED --> PER
  SEC -.observa.-> GOV
  SEC -.detiene.-> EXE
  AUD -.recibe.-> EXP
  AUD -.recibe.-> GOV
  AUD -.recibe.-> EXE
  EVO -.propone versiones.-> COG
```

Los límites de dominio evitan transacciones distribuidas innecesarias. Las decisiones se enlazan mediante identificadores, hashes y recibos.
