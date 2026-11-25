# Plan de Extensión: GPT-RAG Ingestion + Foundry Fabric Data Agent (Híbrido)

## Objetivo
Implementar un modo híbrido que combine:
1. **Indexación NL2SQL batch** (existente en este repo) para recuperación semántica estable.
2. **Consultas en tiempo real a Fabric** mediante Foundry + Fabric Data Agent para analítica viva.

---

## 1. Estado actual del repositorio (baseline)

### 1.1 Ya existe
- Jobs NL2SQL:
  - `jobs/nl2sql_indexer.py`
  - `jobs/nl2sql_purger.py`
- Scheduler para NL2SQL:
  - `CRON_RUN_NL2SQL_INDEX`
  - `CRON_RUN_NL2SQL_PURGE`
- Integraciones Azure base:
  - Blob, AI Search, OpenAI/Foundry endpoint (embeddings)

### 1.2 Gap que se cierra con esta extensión
- Falta consulta directa en vivo sobre Fabric Data Agent desde la API del servicio.

---

## 2. Cambios implementados en código (esqueleto)

## 2.1 Nuevo cliente
- Archivo: `tools/fabric_foundry_agent.py`
- Clase: `FabricFoundryDataAgentClient`
- Función principal: `ask(question, user_token=None)`

Características:
- Crea cliente Foundry (`AIProjectClient`) con `DefaultAzureCredential`.
- Crea versión de agente con `MicrosoftFabricPreviewTool` y `FABRIC_PROJECT_CONNECTION_ID`.
- Ejecuta consulta con `openai.responses.create(...)` y `agent_reference`.

## 2.2 Export en tools
- Archivo: `tools/__init__.py`
- Nuevo export lazy: `FabricFoundryDataAgentClient`

## 2.3 Nuevo endpoint API
- Archivo: `main.py`
- Endpoint:
  - `POST /fabric-data-agent-query`
- Protección:
  - `X-API-KEY` (igual patrón existente)
  - validación opcional de bearer de usuario (`FABRIC_REQUIRE_USER_IDENTITY=true`)

Request:
```json
{
  "question": "What are the top 5 products by revenue this month?"
}
```

Response (shape):
```json
{
  "question": "...",
  "answer": "...",
  "agent": {
    "name": "fabric-data-agent-bridge",
    "version": "...",
    "toolChoiceForced": true
  },
  "identity": {
    "requireUserIdentity": true,
    "tokenProvided": true
  }
}
```

---

## 3. Variables de configuración necesarias

```text
# Foundry/Fabric bridge
FOUNDRY_PROJECT_ENDPOINT=
FOUNDRY_MODEL_DEPLOYMENT_NAME=
FABRIC_PROJECT_CONNECTION_ID=
FABRIC_AGENT_NAME=fabric-data-agent-bridge
FABRIC_AGENT_INSTRUCTIONS=Use the Fabric tool for enterprise data questions.
FABRIC_FORCE_TOOL_CHOICE=true
FABRIC_REQUIRE_USER_IDENTITY=true

# Ya existentes para seguridad API
INGESTION_APP_APIKEY=
```

---

## 4. Roadmap de endurecimiento (recomendado)

## Fase 1 (actual): habilitar camino funcional
- Endpoint y cliente base operativos.
- Prueba de conectividad y respuesta.

## Fase 2: confiabilidad
- Reintentos y timeout explícitos en llamada Foundry.
- Circuit-breaker para fallback automático a búsqueda NL2SQL indexada.
- Métricas de latencia y tasa de error por fuente (Fabric vs fallback).

## Fase 3: seguridad avanzada
- Validación estricta de token de usuario (audiencia, tenant, exp) antes de consulta.
- Auditoría por `user_object_id` y `question_hash`.
- Políticas de datos sensibles por dominio.

## Fase 4: calidad de respuesta
- Router semántico:
  - preguntas de conocimiento -> índices NL2SQL
  - preguntas analíticas vivas -> Fabric Data Agent
- Caching de resultados para consultas repetidas.

---

## 5. Pruebas mínimas sugeridas

1. **Smoke test endpoint**
- Sin `question` -> 400
- Sin `Authorization` y `FABRIC_REQUIRE_USER_IDENTITY=true` -> 401
- Con config incompleta -> 500 con error explícito

2. **Happy path**
- `question` válida + token + conexión fabric configurada -> 200

3. **Fallback readiness**
- Simular error de conexión Foundry y confirmar ruta de fallback (pendiente en Fase 2)

---

## 6. Comandos de verificación rápida

### 6.1 Validar sintaxis Python
```bash
python -m py_compile main.py tools/fabric_foundry_agent.py tools/__init__.py
```

### 6.2 Probar endpoint local
```bash
curl -X POST "http://localhost:8080/fabric-data-agent-query" \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: <api-key>" \
  -H "Authorization: Bearer <user-token>" \
  -d '{"question":"Top 5 cities by profit"}'
```

---

## 7. Riesgos y notas importantes

1. El Fabric tool está en **preview**; revisar cambios de SDK/API.
2. La integración depende de permisos de usuario final sobre Fabric y sus fuentes.
3. Evitar depender solo del modo live; mantener índice batch para continuidad operativa.

---

## 8. Decisión recomendada

Adoptar arquitectura híbrida en producción:
- **Base**: NL2SQL indexado (estable, barato, resiliente).
- **Capa live**: Fabric Data Agent para preguntas frescas y cálculos dinámicos.

Esta combinación maximiza disponibilidad, calidad de respuesta y control de costos.
