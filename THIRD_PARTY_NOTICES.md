# Avisos de código de terceros

## SHEI research source

El diseño de `packages/python/noosfera_core/agent/self_model.py` adapta el patrón
de separación entre capacidades declaradas, observadas y verificadas de:

- Proyecto: `SHEI`
- Repositorio de origen: `https://github.com/fyvjbubj50-glitch/SHEI.git`
- Revisión estudiada: `ed057b689`
- Archivos de referencia principales:
  - `research_python/cognition/self_state/minimum_space_declared_observed.py`
  - `research_python/cognition/system_self_model/self_evidence.py`
- Licencia del origen: Apache License 2.0

La implementación de Noosfera no copia el inventario de sistemas, los estados
afectivos ni las dependencias internas de SHEI. Reimplementa el patrón contra los
manifiestos y endpoints reales de este repositorio, mantiene los tres niveles de
evidencia separados y marca los cambios de comportamiento mediante sus propias
pruebas. La carpeta externa `research_python` permanece sin modificaciones.
