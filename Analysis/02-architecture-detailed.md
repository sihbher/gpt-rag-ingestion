# Arquitectura Detallada de Componentes: GPT-RAG Data Ingestion

## Tabla de contenidos
- [1. Stack Tecnológico Completo](#1-stack-tecnológico-completo)
- [2. Estructura de Directorios](#2-estructura-de-directorios)
- [3. Arquitectura de Componentes](#3-arquitectura-de-componentes)
- [4. Modelo de Datos](#4-modelo-de-datos)
- [5. Flujo de Ejecución de Tareas](#5-flujo-de-ejecución-de-tareas)
- [6. Motor de Procesamiento y Orquestación](#6-motor-de-procesamiento-y-orquestación)
- [7. Modelo de Seguridad](#7-modelo-de-seguridad)
- [8. Comparación de Modos de Despliegue](#8-comparación-de-modos-de-despliegue)
- [9. Patrones de Extensibilidad](#9-patrones-de-extensibilidad)

## 1. Stack Tecnológico Completo

### Backend

| Capa | Tecnología | Versión |
|---|---|---|
| Runtime base del contenedor | Python | 3.12 (imagen bookworm) |
| API HTTP | FastAPI | 0.115.12 |
| Servidor ASGI | Uvicorn | 0.34.2 |
| Scheduler | APScheduler | 3.11.0 |
| Validación payloads | jsonschema | sin pin explícito |
| HTTP async | aiohttp | 3.13.3 |
| OpenAI SDK | openai | 1.55.3 |
| Conteo de tokens | tiktoken | 0.7.0 |
| Splitters de texto | langchain-text-splitters | 0.3.9 |
| Excel parsing | openpyxl | 3.1.5 |
| Tablas markdown | tabulate | 0.9.0 |
| Imágenes | Pillow | 11.1.0 |
| Reintentos | tenacity | 8.5.0 |
| Transcripciones VTT | webvtt-py | 0.5.1 |

### SDKs Azure y servicios conectados

| Área | Librerías |
|---|---|
| Identidad | azure-identity 1.19.0 |
| App Configuration | azure-appconfiguration 1.7.1, azure-appconfiguration-provider 2.1.0 |
| Búsqueda | azure-search-documents 11.5.2 |
| Blob Storage | azure-storage-blob 12.24.1 |
| Key Vault | azure-keyvault-secrets 4.9.0 |
| Cosmos DB | azure-cosmos 4.5.1 |
| Telemetría | azure-monitor-opentelemetry, azure-monitor-opentelemetry-exporter |
| Instrumentación | opentelemetry-instrumentation-fastapi, opentelemetry-instrumentation-httpx 0.52b1 |
| Microsoft Graph | msal (en código) y msgraph-sdk 1.5.4 (dependencia instalada) |

### Frontend

No existe frontend en este repositorio. Es un servicio backend de ingestión y jobs.

### Infraestructura, CI/CD y contenedores

| Categoría | Implementación |
|---|---|
| IaC | Bicep vía azd (archivo local mínimo en infra/main.bicep y dependencia de infraestructura principal en repo GPT-RAG) |
| Orquestación de despliegue | azure.yaml con hooks preprovision y predeploy |
| Scripts de despliegue | scripts/deploy.sh y scripts/deploy.ps1 |
| Imagen contenedor | Dockerfile basado en mcr.microsoft.com/devcontainers/python:3.12-bookworm |
| Publicación de imagen | docker build/push local o az acr build remoto |
| Runtime objetivo | Azure Container Apps |

### Versiones mínimas de runtime

| Runtime | Mínimo observado/recomendado |
|---|---|
| Python | 3.12 |
| Docker | Motor compatible con build linux/amd64 |
| Azure CLI | Requerido por scripts de despliegue |
| Azure Developer CLI (azd) | Requerido por flujo de despliegue |
| PowerShell | Requerido en flujo Windows |

## 2. Estructura de Directorios

### Árbol principal y propósito

```text
gpt-rag-ingestion/
├─ main.py                       # API FastAPI + lifecycle + scheduler + endpoints
├─ dependencies.py               # Inyección de AppConfig y validación X-API-KEY
├─ constants.py                  # Constantes de telemetría/nombre de app
├─ requirements.txt              # Dependencias Python
├─ Dockerfile                    # Imagen y comando de arranque
├─ azure.yaml                    # Definición azd y hooks de despliegue
├─ launch.json                   # Perfil de debugging local
├─ chunking/                     # Motor de chunking y factoría por tipo de archivo
│  ├─ document_chunking.py
│  ├─ chunker_factory.py
│  ├─ exceptions.py
│  └─ chunkers/
│     ├─ base_chunker.py
│     ├─ doc_analysis_chunker.py
│     ├─ multimodal_chunker.py
│     ├─ langchain_chunker.py
│     ├─ spreadsheet_chunker.py
│     ├─ transcription_chunker.py
│     ├─ json_chunker.py
│     └─ nl2sql_chunker.py
├─ jobs/                         # Indexadores y purgers por origen
│  ├─ blob_storage_indexer.py
│  ├─ sharepoint_indexer.py
│  ├─ sharepoint_purger.py
│  ├─ sharepoint_graph_client.py
│  ├─ sharepoint_ingestion_config.py
│  ├─ nl2sql_indexer.py
│  ├─ nl2sql_purger.py
│  └─ multimodal_images_purger.py
├─ tools/                        # Clientes de integración Azure/Graph/OpenAI
│  ├─ appconfig.py
│  ├─ aoai.py
│  ├─ aisearch.py
│  ├─ blob.py
│  ├─ cosmosdb.py
│  ├─ doc_intelligence.py
│  ├─ keyvault.py
│  └─ sharepoint.py
├─ telemetry/                    # Configuración OpenTelemetry + Azure Monitor
├─ utils/                        # Utilidades de archivos y detección de entorno
├─ scripts/                      # Automatización de deploy/preprovision
├─ infra/                        # Punto de entrada IaC de este subrepo
├─ samples/                      # Muestras de documentos y NL2SQL
└─ Analysis/                     # Documentación analítica
```

### Propósito por paquete/módulo

| Módulo | Propósito técnico |
|---|---|
| main.py | Punto de entrada del servicio, health checks, readiness, endpoints de skills, scheduler y wrappers de jobs |
| chunking | Conversión de documentos a chunks con embeddings y metadatos |
| jobs | Sincronización periódica entre fuentes y Azure AI Search, incluyendo limpieza de huérfanos |
| tools | Wrappers de acceso a App Config, OpenAI, AI Search, Blob, Cosmos, Key Vault y Graph |
| telemetry | Logging estructurado e instrumentación OpenTelemetry |
| scripts | Flujo operativo de build y actualización de Container Apps |

## 3. Arquitectura de Componentes

### 3.1 API HTTP (FastAPI)

Responsabilidad principal:
- Exponer endpoints para chunking y embeddings con autenticación por API key.
- Iniciar scheduler y controlar lifecycle de jobs.

Endpoints expuestos:

| Método | Ruta | Autenticación | Descripción |
|---|---|---|---|
| GET | / | No | Estado básico con nombre y versión |
| GET | /healthz | No | Liveness probe |
| GET | /readyz | No | Readiness probe (verifica inicialización de AppConfig) |
| POST | /document-chunking | X-API-KEY | Descarga documento, aplica chunker por tipo y devuelve chunks |
| POST | /text-embedding | X-API-KEY | Genera embeddings para textos de entrada |

Dependencias externas:
- App Configuration para cron/config.
- Blob Storage para descargar documentos.
- Azure OpenAI para embeddings.
- Application Insights/Azure Monitor para telemetría.

Flujo interno (ASCII):

```text
Request -> Validación schema/API key -> Enriquecimiento input -> Chunking/Embedding -> Response JSON
```

### 3.2 Scheduler y Orquestación de Jobs

Responsabilidad principal:
- Programar y ejecutar tareas periódicas (indexación y purga).

Jobs registrados:
- run_blob_index
- run_blob_purge
- run_sharepoint_index
- run_sharepoint_purge
- run_nl2sql_index
- run_nl2sql_purge
- run_images_purge (solo si MULTIMODAL true)

Dependencias externas:
- App Configuration para expresiones CRON.
- Servicios Azure invocados por cada job específico.

Flujo interno (ASCII):

```text
Lifespan startup -> Carga cron desde AppConfig -> Scheduler.add_job -> Ejecución periódica
```

### 3.3 Blob Indexer y Blob Purger

Responsabilidad principal:
- Indexador: detectar blobs nuevos/modificados, chunkear y upsert en AI Search.
- Purger: borrar documentos de índice cuyo blob ya no existe.

Interfaces:
- BlobStorageDocumentIndexer.run()
- BlobStorageDeletedItemsCleaner.run()

Servicios cloud usados:
- Blob Storage: lectura de origen, escritura de logs/runs, staging opcional.
- Azure AI Search: búsqueda, borrado, upload_documents en lotes.
- Azure OpenAI (vía chunkers): embedding de contenido.

Flujo interno (ASCII):

```text
List blobs -> Detecta cambios por last_modified -> Chunking -> Delete parent docs -> Upload batches -> Run summary
```

### 3.4 SharePoint Indexer y SharePoint Purger

Responsabilidad principal:
- Indexer: consumir listas SharePoint (incluye lookup fields y adjuntos), generar docs e indexar.
- Purger: detectar ítems eliminados en SharePoint y purgar docs derivados del índice.

Interfaces:
- SharePointIndexer.run()
- SharePointPurger.run()
- SharePointGraphClient.iter_items(...), iter_item_ids(...)

Servicios cloud usados:
- Microsoft Graph para lectura de listas/items/permissions/adjuntos.
- Key Vault para secreto de app de Graph.
- Cosmos DB para catálogo de sites/listas.
- Azure AI Search y Blob Storage para índices y logs.

Flujo interno (ASCII):

```text
Cosmos datasource config -> Graph list items -> Freshness check -> Body doc + attachment chunks -> AI Search
```

### 3.5 NL2SQL Indexer y Purger

Responsabilidad principal:
- Indexar JSONs de queries/tables/measures hacia índices dedicados de AI Search.
- Purgar documentos de índice no existentes en Blob.

Interfaces:
- NL2SQLIndexer.run(), _process_one(...)
- NL2SQLPurger.run(), _purge_one_index(...)

Servicios cloud usados:
- Blob Storage (container nl2sql).
- Azure OpenAI (embeddings de question/description).
- Azure AI Search (índices por tipo).

Flujo interno (ASCII):

```text
List blobs nl2sql/* -> Parse JSON -> Build doc + embedding -> Index target (queries/tables/measures)
```

### 3.6 Capa de Integración (tools)

Responsabilidad principal:
- Encapsular autenticación y acceso a servicios Azure/Graph.

Componentes:
- AppConfigClient
- AzureOpenAIClient
- AISearchClient
- BlobClient / BlobContainerClient
- KeyVaultClient
- CosmosDBClient
- DocumentIntelligenceClient

Patrón común:
- ChainedTokenCredential con Managed Identity + Azure CLI fallback.

## 4. Modelo de Datos

### 4.1 Documento de índice RAG (Blob/SharePoint)

Colección/índice:
- Azure AI Search index principal (SEARCH_RAG_INDEX_NAME o AI_SEARCH_INDEX_NAME)

Campos observados:

| Campo | Tipo | Descripción |
|---|---|---|
| id | string | Clave única por chunk |
| parent_id | string | Identificador del documento fuente |
| metadata_storage_path | string | Ruta lógica origen |
| metadata_storage_name | string | Nombre archivo/ítem |
| metadata_storage_last_modified | datetime/string | Última modificación del origen |
| metadata_security_user_ids | string[] | Principales de usuario para ACL trimming |
| metadata_security_group_ids | string[] | Principales de grupo para ACL trimming |
| metadata_security_rbac_scope | string | Scope de RBAC (blob indexer) |
| chunk_id | int | Número de chunk |
| content | string | Texto del chunk |
| contentVector | float[] | Embedding principal |
| captionVector | float[] | Embedding de captions (multimodal) |
| imageCaptions | string | Texto de captions de imágenes |
| relatedImages | string[] | URLs de imágenes asociadas |
| relatedFiles | string[] | Referencias a archivos relacionados |
| title | string | Título lógico |
| page | int | Página origen |
| offset | int | Offset de contenido |
| length | int | Longitud en caracteres |
| summary | string | Resumen (si aplica) |
| category | string | Categoría de negocio |
| filepath | string | Ruta relativa en origen |
| url | string | URL de origen |
| source | string | blob o sharepoint-list |

Índices/keys:
- Key documental: id.
- Clave de agrupación lógica: parent_id.
- No se define partition key en Azure AI Search.

Ejemplo JSON representativo:

```json
{
  "id": "documents-manual-pdf-c00000",
  "parent_id": "/documents/manual.pdf",
  "metadata_storage_name": "manual.pdf",
  "metadata_storage_last_modified": "2026-04-01T05:11:10Z",
  "metadata_security_user_ids": ["11111111-1111-1111-1111-111111111111"],
  "metadata_security_group_ids": ["22222222-2222-2222-2222-222222222222"],
  "chunk_id": 0,
  "content": "Contenido del chunk...",
  "contentVector": [0.0123, -0.0441, 0.0199],
  "title": "Manual",
  "page": 1,
  "source": "blob"
}
```

### 4.2 Catálogo de fuentes SharePoint en Cosmos DB

Container:
- COSMOS_DATASOURCES_CONTAINER (default: datasources)

Documento esperado (tipo sharepoint_site):

| Campo | Tipo | Descripción |
|---|---|---|
| id | string | Id del documento de configuración |
| type | string | Debe ser sharepoint_site |
| siteDomain | string | Dominio del tenant SharePoint |
| siteName | string | Nombre del sitio |
| category | string | Categoría por defecto |
| lists | array | Configuraciones por lista |

Dentro de lists[]:

| Campo | Tipo | Descripción |
|---|---|---|
| listId | string | Id de lista (preferido) |
| listName | string | Nombre lista (legacy fallback) |
| listType | string | documentLibrary o genericList |
| includeFields | string[] | Campos permitidos |
| excludeFields | string[] | Campos excluidos |
| filter | string | OData filter |
| category | string | Categoría específica |

Ejemplo JSON representativo:

```json
{
  "id": "sp-site-01",
  "type": "sharepoint_site",
  "siteDomain": "contoso.sharepoint.com",
  "siteName": "Legal",
  "category": "Políticas",
  "lists": [
    {
      "listId": "a1b2c3d4-e5f6-...",
      "listType": "documentLibrary",
      "includeFields": ["Title", "Modified"],
      "excludeFields": ["Editor"],
      "filter": "fields/Status eq 'Published'"
    }
  ]
}
```

### 4.3 Documentos NL2SQL en Blob y AI Search

Fuente Blob:
- Container nl2sql con carpetas queries/, tables/, measures/.

Ejemplos reales de entrada:

```json
{
  "datasource": "adventureworks",
  "question": "What are the top 5 most expensive products currently available for sale?",
  "query": "SELECT TOP 5 ...",
  "reasoning": "This query retrieves..."
}
```

```json
{
  "table": "SalesLT.Customer",
  "datasource": "adventureworks",
  "description": "Contains personal and business information related to customers.",
  "columns": [{"name": "CustomerID", "description": "Primary key..."}]
}
```

Índices destino:
- SEARCH_QUERIES_INDEX_NAME
- SEARCH_TABLES_INDEX_NAME
- SEARCH_MEASURES_INDEX_NAME

Campos indexados (según tipo):

| Tipo | Campos principales |
|---|---|
| queries | id, datasource, question, query, reasoning, contentVector |
| tables | id, table, datasource, description, columns, contentVector |
| measures | id, datasource, name, description, type, source_table, data_type, source_model, contentVector |

### 4.4 Logs técnicos en Blob (jobs container)

Entidad operativa:
- Logs por archivo y resumen por corrida en blobs JSON.

Rutas típicas:
- blob-storage-indexer/runs/{runId}.json
- sharepoint-indexer/runs/{runId}.json
- sharepoint-purger/runs/{runId}.json
- nl2sql-indexer/runs/{runId}.json
- blob-storage-purger/runs/{timestamp}.json

## 5. Flujo de Ejecución de Tareas

### Flujo técnico principal (startup a operación)

1. Arranque del proceso:
   - FastAPI entra en lifespan.
   - _ensure_auth_or_exit valida disponibilidad de autenticación (MI/SP/CLI).
2. Inicialización de configuración:
   - get_config crea AppConfigClient.
   - AppConfigClient carga labels gpt-rag-ingestion, gpt-rag y null-label.
3. Inicialización de observabilidad:
   - Telemetry.configure_monitoring configura Azure Monitor y logging.
4. Arranque de scheduler:
   - _schedule lee claves CRON_RUN_*.
   - Registra jobs con CronTrigger.
5. Ejecución periódica:
   - Se invocan run_blob_index, run_sharepoint_index, etc.
6. Persistencia de resultados:
   - Cada job escribe run summaries y file logs.

### Flujo técnico de indexación Blob

1. BlobStorageDocumentIndexer.run lista blobs fuente.
2. _load_latest_index_state obtiene estado actual de index.
3. Se calculan candidatos por comparación last_modified.
4. _process_one procesa cada blob:
   - Descarga blob
   - Construye data para chunker
   - _iter_search_docs_for_blob transforma chunks a docs de índice
   - _replace_parent_docs_stream o _replace_parent_docs_via_staging
5. _upload_iter_in_batches envía lotes a AI Search.
6. _write_run_summary persiste resumen.

### Manejo de errores, reintentos y timeout

| Área | Estrategia |
|---|---|
| AI Search | _with_backoff con hasta 8 intentos y lectura de retry-after-ms/Retry-After |
| Azure OpenAI | reintentos exponenciales en tools/aoai.py; adicionalmente sharepoint indexer gestiona RateLimitError con semáforo y backoff |
| Item processing SharePoint | asyncio.wait_for con INDEXER_ITEM_TIMEOUT_SECONDS |
| Run summary write | timeout total con _write_run_summary_safely |
| Conectividad Blob/Search/Graph | manejo de excepciones y continuidad best-effort en logs/pointers |

## 6. Motor de Procesamiento y Orquestación

### Motor interno

No existe un workflow engine externo; el motor interno está compuesto por:
- APScheduler para orquestación temporal.
- Jobs asíncronos especializados por fuente.
- Factoría de chunkers para routing por tipo de archivo.

### Clases base y contratos de extensión

Clase base:

```python
class BaseChunker:
    def __init__(self, data):
        ...

    def get_chunks(self):
        pass

    def _create_chunk(self, chunk_id, content, summary="", embedding_text="", title="", page=0, offset=0, related_images=None, related_files=None):
        ...
```

Contrato práctico para nuevos chunkers:
- Heredar de BaseChunker.
- Implementar get_chunks(self) y devolver List[Dict[str, Any]].
- Cada dict debe ser compatible con _to_search_doc / _doc_for_attachment_chunk.

### Ciclo de vida de un componente

```text
Init config/credential -> Ensure clients -> Run loop -> Write logs/summaries -> Close clients
```

### Sistema de condiciones y routing

Reglas principales:
- ChunkerFactory selecciona chunker por extensión.
- MULTIMODAL habilita/deshabilita chunker multimodal y purger de imágenes.
- listType de SharePoint define si procesa solo body o también adjuntos.
- Freshness check evita reindexación cuando no hay cambios.

### Sistema de eventos o pub-sub

No hay bus pub-sub interno (Event Grid, Service Bus o similar) en este repositorio.
El patrón es polling programado + ejecución por cron.

## 7. Modelo de Seguridad

### Identidades utilizadas

| Contexto | Identidad |
|---|---|
| Runtime principal | Managed Identity (system o user-assigned) |
| Desarrollo local | Azure CLI credential fallback |
| SharePoint Graph | Service Principal (client_id + secret en Key Vault) |
| Despliegue | Identidad del operador/CI con permisos sobre ACR y Container Apps |

### RBAC sugerido por operación

Tabla inferida a partir de llamadas SDK/CLI observadas:

| Identidad | Role | Scope |
|---|---|---|
| Managed Identity de Container App | App Configuration Data Reader | App Configuration |
| Managed Identity de Container App | Key Vault Secrets User | Key Vault |
| Managed Identity de Container App | Storage Blob Data Contributor | Storage Account/containers usados |
| Managed Identity de Container App | Search Index Data Contributor | Azure AI Search service/index |
| Managed Identity de Container App | Cognitive Services User | Azure OpenAI / AI Foundry resource |
| Managed Identity de Container App | Cosmos DB Built-in Data Reader (mínimo) | Cosmos DB account/database/container |
| Identity de Container App para pull | AcrPull | Azure Container Registry |
| Service Principal SharePoint | Permisos Graph de lectura sobre sites/lists/items/files | Microsoft Graph tenant scope |

### Flujo de autenticación entre servicios

```text
Container App MI -> Entra token -> Azure SDK clients (Search/Blob/AppConfig/KeyVault/OpenAI/Cosmos)
SharePoint SP -> MSAL token -> Microsoft Graph API
```

### Gestión de secretos y configuración sensible

- Configuración central en App Configuration.
- Secretos sensibles (ej. sharepointClientSecret) en Key Vault.
- APP_CONFIG_ENDPOINT es bootstrap obligatorio.
- Validación de acceso API por cabecera X-API-KEY contra INGESTION_APP_APIKEY.

## 8. Comparación de Modos de Despliegue

### Tabla comparativa

| Característica | Modo Básico | Modo Enterprise |
|---|---|---|
| Exposición de servicios | Endpoints públicos controlados | Private Endpoints + acceso interno |
| Red | Sin VNet obligatoria | VNet segmentada por subredes |
| Seguridad | API key + MI | ACL trimming, RBAC granular, aislamiento de red, rotación de secretos |
| Escalado | Autoscaling default | Perfiles dedicados y límites por workload |
| Observabilidad | Logs estándar | Dashboards, alertas, SLO y correlación distribuida |
| Resiliencia | Configuración mínima | Estrategias HA/DR y políticas operativas |

### Cambios por recurso en modo enterprise

| Recurso | Cambio | Justificación |
|---|---|---|
| Azure Container Apps | Integración VNet + perfiles dedicados | Aislamiento y capacidad predecible |
| Azure AI Search | Private Endpoint + SKU superior (S1/S2) | Seguridad de red y capacidad |
| Azure OpenAI | Private access y control de cuota | Reducir exposición y estabilizar throughput |
| Storage Account | Private Endpoint + firewall + deshabilitar público | Protección de datos y compliance |
| Key Vault | Private Endpoint + RBAC puro + soft delete/purge protection | Seguridad de secretos |
| App Configuration | Private Endpoint + replicas según criticidad | Configuración segura y resiliente |
| Cosmos DB | Private Endpoint + throughput administrado | Latencia estable y seguridad |
| Monitor/App Insights | Workspace centralizado + alertas | Operación enterprise y auditoría |

### Topología de red enterprise (ASCII)

```text
                    +------------------------+
                    | Corporate Network/VPN  |
                    +-----------+------------+
                                |
                             Private DNS
                                |
       +-------------------------------------------------------+
       | VNet                                                   |
       |  +------------------+   +---------------------------+  |
       |  | Subnet Apps      |   | Subnet Private Endpoints  |  |
       |  | Container Apps   |---| PE: Search/OpenAI/Blob/   |  |
       |  | Ingestion API    |   | AppConfig/KeyVault/Cosmos |  |
       |  +------------------+   +---------------------------+  |
       +-------------------------------------------------------+
                                |
                         Azure Monitor
```

## 9. Patrones de Extensibilidad

### 9.1 Añadir un nuevo chunker/plugin

Paso a paso:
1. Crear clase en chunking/chunkers heredando BaseChunker.
2. Implementar get_chunks(self).
3. Registrar selección en chunking/chunker_factory.py.
4. Asegurar salida compatible con campos esperados por indexadores.
5. Probar con endpoint /document-chunking.

Firma clave:

```python
def get_chunks(self) -> list[dict]:
    ...
```

### 9.2 Añadir un nuevo indexador

Paso a paso:
1. Crear archivo en jobs con clase y método run async.
2. Implementar ensure_clients, flujo de lectura fuente, indexación y summary.
3. Agregar wrapper run_nuevo_job en main.py.
4. Registrar CRON_RUN_* en App Configuration.
5. Incluir import/export en jobs/__init__.py si aplica.

Firma clave:

```python
class MiIndexer:
    async def run(self) -> None:
        ...
```

### 9.3 Registrar nuevas fuentes en catálogo

SharePoint:
- Insertar documento type=sharepoint_site en container datasources de Cosmos.
- Definir siteDomain, siteName y lists con listId/listType/filter/includeFields/excludeFields.

NL2SQL:
- Subir nuevos JSON bajo nl2sql/queries, nl2sql/tables o nl2sql/measures.
- Asegurar que índices destino estén configurados.

### 9.4 Contribuir al proyecto (flujo recomendado)

1. Preparar entorno local con Python 3.12, Azure CLI y azd.
2. Configurar APP_CONFIG_ENDPOINT y autenticación (az login o MI).
3. Ejecutar/debug local con launch.json en puerto 8080.
4. Validar endpoints y corridas de jobs en entorno de prueba.
5. Desplegar con azd deploy (infra se gestiona en el repo principal GPT-RAG).
6. Seguir plantilla de PR en docs/pull_request_template.md.

### 9.5 Notas de arquitectura relevantes

- Este repositorio no contiene AGENTS.md ni definición de frontend.
- La IaC local es un entrypoint mínimo; la infraestructura completa vive fuera de este subrepo.
- Existen patrones de robustez ya incorporados: throttling-aware retries, timeouts por item, y logs estructurados por corrida/item.
