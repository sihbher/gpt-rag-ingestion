# 00-full-analysis — GPT-RAG Data Ingestion

## Tabla de contenidos

- [1. ¿Qué es GPT-RAG Data Ingestion?](#1-qué-es-gpt-rag-data-ingestion)
- [2. Conceptos Clave](#2-conceptos-clave)
- [3. Capacidades Completas](#3-capacidades-completas)
- [4. Prerrequisitos](#4-prerrequisitos)
- [5. Arquitectura Final](#5-arquitectura-final)
- [6. Fuera de Alcance](#6-fuera-de-alcance)
- [7. Escenarios de Ejemplo](#7-escenarios-de-ejemplo)
- [8. Índice de Samples Incluidos](#8-índice-de-samples-incluidos)
- [9. Soporte de Despliegue con IaC (Infrastructure as Code)](#9-soporte-de-despliegue-con-iac-infrastructure-as-code)

---

## 1. ¿Qué es GPT-RAG Data Ingestion?

**Descripción en una frase**  
GPT-RAG Data Ingestion es un servicio FastAPI que orquesta ingestión, chunking multimodal y generación de embeddings para indexar contenido empresarial en Azure AI Search.

**Propuesta de valor principal**
- Unifica pipelines de ingestión para Blob Storage, SharePoint y NL2SQL.
- Aplica chunking especializado por tipo de archivo (PDF, Office, imágenes, VTT, JSON, Excel, Markdown, etc.).
- Genera embeddings de texto e imágenes para recuperación semántica y escenarios multimodales en RAG.
- Ejecuta procesos batch con cron (indexación y purga) y expone endpoints HTTP para skills personalizadas de AI Search.

**Repositorio, licencia, runtime**
- Repositorio: https://github.com/Azure/gpt-rag-ingestion (parte de https://github.com/Azure/gpt-rag)
- Licencia: MIT
- Runtime principal:
  - Python 3.12 (imagen base `mcr.microsoft.com/devcontainers/python:3.12-bookworm`)
  - FastAPI + Uvicorn
  - Contenedor expuesto en puerto 8080

---

## 2. Conceptos Clave

### 2.1 Documento de entrada canónico
Cada flujo termina normalizando el input a un contrato común para chunking:
- `documentUrl`
- `documentContentType`
- `documentBytes`
- opcionales: `documentSasToken`, `fileName`, `documentContent`

```python
input_data = {
    "documentUrl": "https://<storage>.blob.core.windows.net/documents/manual.pdf",
    "documentContentType": "application/pdf",
    "documentBytes": b"...",
    "fileName": "manual.pdf"
}
chunks, errors, warnings = DocumentChunker().chunk_documents(input_data)
```

### 2.2 Fábrica de chunkers
`ChunkerFactory` selecciona estrategia por extensión y flags (`MULTIMODAL`, versión Doc Intelligence).

```python
extension = get_file_extension(filename)
if extension == "vtt":
    return TranscriptionChunker(data)
elif extension in ("xlsx", "xls"):
    return SpreadsheetChunker(data)
elif extension in ("pdf", "png", "jpg"):
    return MultimodalChunker(data) if multimodality else DocAnalysisChunker(data)
```

### 2.3 Chunk enriquecido
Cada chunk transporta metadata + vectores:
- `content`, `summary`, `title`, `page`, `offset`
- `contentVector`, `captionVector`
- `relatedImages`, `relatedFiles`

```python
chunk = {
    "chunk_id": 0,
    "content": "...",
    "contentVector": [...],
    "captionVector": [...],
    "relatedImages": []
}
```

### 2.4 Jobs programados
`APScheduler` ejecuta indexadores/purgers por cron configurable desde App Configuration.

```yaml
CRON_RUN_BLOB_INDEX: "0 * * * *"
CRON_RUN_BLOB_PURGE: "10 * * * *"
RUN_JOBS_ON_STARTUP: "true"
```

### 2.5 Cliente de configuración central
`AppConfigClient` abstrae acceso a settings con prioridades:
1. Azure App Configuration (labels `gpt-rag-ingestion`, `gpt-rag`, null)
2. Connection string fallback
3. Variables de entorno

### 2.6 Seguridad por identidad administrada y AAD
Patrón transversal:
- `ChainedTokenCredential(ManagedIdentityCredential, AzureCliCredential)`
- Sin secrets embebidos en código
- `X-API-KEY` para endpoints HTTP de skill

### 2.7 Tipos de procesos
- API síncrona/asíncrona: `/document-chunking`, `/text-embedding`
- Worker cron: indexadores y purgers
- Integraciones externas: Graph, AI Search, Blob, Cosmos, Key Vault, Azure OpenAI/Foundry

### 2.8 Relación entre conceptos
1. Trigger (cron o HTTP) -> 2) lectura de fuente -> 3) normalización de documento -> 4) chunking especializado -> 5) embeddings -> 6) upsert/purge en AI Search -> 7) logging/telemetría en App Insights + blobs de jobs.

---

## 3. Capacidades Completas

### 3.1 API HTTP (FastAPI)

| Endpoint | Método | Descripción detallada | Input | Output | Seguridad |
|---|---|---|---|---|---|
| `/` | GET | Estado básico del servicio con nombre y versión | N/A | `{status,name,version}` | Pública |
| `/healthz` | GET | Liveness probe sin dependencias externas | N/A | `{status:"ok"}` | Pública |
| `/readyz` | GET | Readiness: valida inicialización de config | N/A | `200 ready` o `503 not ready` | Pública |
| `/document-chunking` | POST | Descarga documento desde blob URL, ejecuta chunking especializado y devuelve chunks para skillset | JSON skill request (`values[]`) | JSON con `chunks/errors/warnings` | `X-API-KEY` |
| `/text-embedding` | POST | Genera embedding para texto de entrada | JSON con `values[].data.text` | JSON con `embedding` por item | `X-API-KEY` |

### 3.2 Motor de chunking

| Componente | ID técnico | Descripción | Inputs | Outputs | Configuración clave |
|---|---|---|---|---|---|
| Orquestador | `DocumentChunker` | Punto de entrada para chunking; maneja errores/warnings y formato de respuesta | `data` normalizado | `chunks, errors, warnings` | N/A |
| Fábrica | `ChunkerFactory` | Selecciona chunker por extensión y capacidades | `data` | instancia de chunker | `MULTIMODAL`, `DOC_INTELLIGENCE_API_VERSION` |
| Base abstracta | `BaseChunker` | Normaliza metadata, crea chunk estándar, genera embeddings | `data` | `chunk dict` | `EMBEDDINGS_VECTOR_DIMENSIONS` |
| Documento AI | `DocAnalysisChunker` | Usa Document Intelligence + splitters token-aware | bytes de doc | chunks por página/sección | `CHUNKING_NUM_TOKENS`, `CHUNKING_MIN_CHUNK_SIZE`, `TOKEN_OVERLAP` |
| Multimodal | `MultimodalChunker` | Extrae/adjunta figuras, captioning, embeddings de caption, persistencia en blob de imágenes | documento analizado + figuras | chunks con `relatedImages/captionVector` | `DOCUMENTS_IMAGES_STORAGE_CONTAINER`, `MINIMUM_FIGURE_AREA_PERCENTAGE` |
| Genérico texto/código | `LangChainChunker` | Chunking para md/txt/html/py/csv/xml con splitters de LangChain | bytes texto | chunks | `CHUNKING_*` |
| JSON semántico | `JSONChunker` | Particionado recursivo preservando JSON válido | bytes JSON | chunks JSON válidos | `CHUNKING_*` |
| Spreadsheet | `SpreadsheetChunker` | Modo por hoja o por fila con tabulación y resumen opcional | `.xlsx/.xls` | chunks por hoja/fila | `SPREADSHEET_CHUNKING_NUM_TOKENS`, `SPREADSHEET_CHUNKING_BY_ROW*` |
| Transcripción | `TranscriptionChunker` | Procesa VTT, conserva turnos de voz y resume conversación | `.vtt` | chunks + summary | `CHUNKING_NUM_TOKENS` |
| NL2SQL local | `NL2SQLChunker` | Convierte JSON de preguntas/queries a chunks por entrada | `.nl2sql/.json` | chunks con embedding de pregunta | `CHUNKING_NUM_TOKENS` |

### 3.3 Workers / procesos batch

| Proceso | ID | Función | Fuente | Destino | Notas |
|---|---|---|---|---|---|
| Blob indexer | `BlobStorageDocumentIndexer` | Reindex incremental por `last_modified`; chunking + upload | Blob container de documentos | AI Search index RAG | Mantiene logs por archivo y resumen por corrida |
| Blob purger | `BlobStorageDeletedItemsCleaner` | Limpia chunks huérfanos de blobs eliminados | Estado blob vs índice | AI Search | Exportado desde `jobs/__init__.py` |
| SharePoint indexer | `SharePointIndexer` | Ingesta listas/bibliotecas desde Graph; adjuntos y cuerpos | SharePoint + Graph + Cosmos config | AI Search + logs blob | Soporta ACL/RBAC metadata |
| SharePoint purger | `SharePointPurger` | Elimina docs cuyo item fuente ya no existe | Graph IDs + AI Search | AI Search | Escaneo paginado |
| NL2SQL indexer | `NL2SQLIndexer` | Indexa `queries/`, `tables/`, `measures/` con embeddings | Blob `nl2sql` | 3 índices AI Search | IDs sanitizados por path |
| NL2SQL purger | `NL2SQLPurger` | Borra documentos huérfanos en índices NL2SQL | Blob `nl2sql` | índices NL2SQL | Compara set existente |
| Imágenes purger | `ImagesDeletedFilesPurger` | Borra imágenes no referenciadas por chunks | Container imágenes + campo `relatedImages` | Blob imágenes | Previene crecimiento de costo/almacenamiento |

### 3.4 SDK wrappers / conectores

| Módulo | Clase(s) | Capacidad |
|---|---|---|
| `tools/appconfig.py` | `AppConfigClient` | Config centralizada y resolución de secretos vía Key Vault references |
| `tools/aoai.py` | `AzureOpenAIClient`, `GptTokenEstimator` | Chat completions + embeddings + retries robustos 429 |
| `tools/aisearch.py` | `AISearchClient` | CRUD/search async para índices AI Search |
| `tools/blob.py` | `BlobClient`, `BlobContainerClient` | Lectura/escritura/listado/delete en Blob Storage |
| `tools/doc_intelligence.py` | `DocumentIntelligenceClient` | Análisis OCR/layout con salida markdown/figures |
| `tools/keyvault.py` | `KeyVaultClient` | Lectura de secretos |
| `tools/cosmosdb.py` | `CosmosDBClient` | Lectura/escritura de documentos (config SharePoint) |
| `tools/sharepoint.py` | `SharePointMetadataStreamer` | Enumeración streaming de archivos SharePoint |

### 3.5 Configuración y utilidades

| Archivo | Propósito |
|---|---|
| `dependencies.py` | Inyección de dependencias y validación API key |
| `constants.py` | Constantes de app y App Insights key name |
| `utils/file_utils.py` | Helpers de path/extensión/nombre |
| `utils/tools.py` | Detección de entorno Azure |
| `telemetry/telemetry.py` | OpenTelemetry + Azure Monitor + filtros de logging |

### 3.6 Capacidades de framework/pipeline
- Soporte de ingestión incremental (detección de cambios por timestamp/etag).
- Soporte de purga para consistencia eventual del índice.
- Reintentos y backoff en dependencias con throttling (OpenAI, Search, Graph).
- Observabilidad estructurada: eventos JSON y trazas OTel.
- Scheduling configurable por cron en runtime sin recompilar.

### 3.7 Características de UI
- No existe UI frontend en este repositorio.
- Superficie de interacción: endpoints HTTP + logs + Azure CLI/scripts.

### 3.8 Características de API
- API FastAPI versionada por archivo `VERSION`.
- Diseñada para integración con Custom Skills de Azure AI Search.
- Endpoints principales protegidos con `X-API-KEY`.

### 3.9 Características de workers/procesos
- Workers asíncronos con `asyncio` + SDKs async de Azure.
- Concurrencia configurable (`INDEXER_MAX_CONCURRENCY`, semáforos internos).
- Persistencia de auditoría de runs en contenedor `jobs`.

### 3.10 Extensibilidad (componentes personalizados)

**Crear nuevo chunker**
1. Implementar clase heredando `BaseChunker`.
2. Definir `get_chunks()` y usar `_create_chunk(...)`.
3. Registrar extensión/ruta en `ChunkerFactory.get_chunker()`.

```python
from chunking.chunkers.base_chunker import BaseChunker

class MyCustomChunker(BaseChunker):
    def get_chunks(self):
        text = self.decode_to_utf8(self.document_bytes)
        return [self._create_chunk(chunk_id=0, content=text)]
```

**Crear nuevo worker**
1. Crear módulo en `jobs/` con clase `run()` async.
2. Agregar wrapper `run_<job>()` en `main.py`.
3. Registrar cron key en `lifespan()`.

---

## 4. Prerrequisitos

### 4.1 Servicios cloud requeridos (Azure)

| Servicio | Uso | SKU recomendado (referencia) |
|---|---|---|
| Azure Container Apps | Hosting de API/worker | Consumption o Workload profile según carga |
| Azure App Configuration | Configuración central | Standard |
| Azure Key Vault | Secretos y credenciales Graph | Standard |
| Azure Storage Account (Blob) | Fuente documentos, logs jobs, imágenes | Standard v2 (Hot/LRS inicialmente) |
| Azure AI Search | Índices RAG y NL2SQL | S1+ (o superior según volumen/vector dims) |
| Azure OpenAI / Azure AI Foundry | Embeddings y completions | Despliegues `text-embedding-*` y chat compatibles |
| Azure AI Document Intelligence | OCR/layout/figures | Standard (API 2024-11-30+) |
| Azure Cosmos DB | Configuración de fuentes SharePoint | SQL API |
| Application Insights / Azure Monitor | Telemetría y trazas | Baseline por entorno |
| Microsoft Graph + Entra ID app | Acceso SharePoint | Permisos app Graph |

### 4.2 Toolchain de desarrollo

| Herramienta | Versión mínima sugerida |
|---|---|
| Python | 3.12 |
| Docker | Engine compatible Linux/amd64 |
| Azure CLI | 2.57+ |
| Azure Developer CLI (`azd`) | 1.10+ |
| Git | 2.40+ |

Dependencias Python en `requirements.txt` (FastAPI, Azure SDK, OpenAI, LangChain splitters, etc.).

### 4.3 Permisos y roles necesarios
- **Managed Identity / SPN del servicio**:
  - Storage Blob Data Contributor (contenedores de documentos/jobs/imágenes)
  - Search Index Data Contributor (índices AI Search)
  - App Configuration Data Reader
  - Key Vault Secrets User
  - Cognitive Services User (Azure OpenAI/Foundry, Doc Intelligence)
  - Cosmos DB Data Reader/Contributor (según operación)
- **Microsoft Graph app permissions** (para SharePoint): lectura de sitios/listas/drive items según alcance configurado.

### 4.4 Cuotas y límites relevantes
- TPM/RPM de embeddings y chat (impacta jobs masivos, especialmente hojas de cálculo).
- Límite de dimensiones vectoriales (`EMBEDDINGS_VECTOR_DIMENSIONS`).
- Tamaño de lote en AI Search (`INDEXER_BATCH_SIZE` recomendado <= 500).
- Tamaño de documento y throughput de Document Intelligence.
- Concurrencia de workers por configuración (`INDEXER_MAX_CONCURRENCY`).

---

## 5. Arquitectura Final

### 5.1 Diagrama de componentes (ASCII)

```text
                   +------------------------------+
                   | Azure App Configuration      |
                   | + Key Vault references       |
                   +--------------+---------------+
                                  |
                                  v
+--------------------+   +--------+---------+   +----------------------+
| Scheduler (cron)   |-->| FastAPI Service  |-->| Azure Monitor / AI   |
| APScheduler        |   | main.py          |   | (logs + traces)      |
+---------+----------+   +---+----------+---+   +----------------------+
          |                  |          |
          |                  |          +--> /text-embedding (HTTP)
          |                  |
          |                  +--> /document-chunking (HTTP)
          |
          +--> Jobs:
               - Blob index/purge
               - SharePoint index/purge
               - NL2SQL index/purge
               - Images purge

Data plane dependencies:
  Blob Storage <-> Chunkers <-> Azure OpenAI/Foundry
                 |            \-> Document Intelligence
                 \-> Azure AI Search (index/upsert/delete)

SharePoint plane:
  Microsoft Graph + Key Vault + Cosmos (site configs)
```

### 5.2 Mapa de comunicación entre servicios

| Origen | Destino | Protocolo/puerto | Propósito |
|---|---|---|---|
| Cliente / AI Search skillset | FastAPI (`/document-chunking`) | HTTPS 443 | Chunking on-demand |
| Cliente / AI Search skillset | FastAPI (`/text-embedding`) | HTTPS 443 | Embeddings on-demand |
| FastAPI/Workers | Azure App Configuration | HTTPS 443 | Leer configuración |
| FastAPI/Workers | Azure Key Vault | HTTPS 443 | Obtener secretos |
| Chunkers/Workers | Azure OpenAI/Foundry endpoint | HTTPS 443 | Embeddings y completions |
| Chunkers | Document Intelligence | HTTPS 443 | OCR/layout/figures |
| Workers | Azure Blob Storage | HTTPS 443 | Leer documentos / escribir logs / imágenes |
| Workers | Azure AI Search | HTTPS 443 | Upsert/delete/search documentos |
| SharePoint jobs | Microsoft Graph | HTTPS 443 | Leer listas, items, adjuntos |
| SharePoint jobs | Azure Cosmos DB | HTTPS 443 | Leer configuración de sites/lists |

### 5.3 Flujo de datos E2E
1. Documento entra por Blob/SharePoint o request HTTP.
2. Se descargan bytes y metadata mínima.
3. `ChunkerFactory` selecciona chunker por tipo.
4. Chunker produce chunks + embeddings (`contentVector`, opcional `captionVector`).
5. Worker sube chunks a AI Search (upsert) y purga obsoletos.
6. Se registran logs por item y resumen por run en blob `jobs`.
7. Telemetría fluye a Azure Monitor/Application Insights.

### 5.4 Ciclo de vida de una tarea (trigger -> resultado)
- **Startup**: valida autenticación, inicializa config y scheduler.
- **Scheduling**: registra cron jobs según keys de App Config.
- **Ejecución**: cada job recorre fuentes y decide incremental/purge.
- **Transformación**: chunking + enriquecimiento semántico.
- **Persistencia**: índice actualizado + logs de ejecución.
- **Observabilidad**: eventos estructurados para troubleshooting.

### 5.5 Esquema de base de datos (si aplica)
No existe RDBMS propia del servicio. Persistencias:
- Azure AI Search (índices documentales/vectoriales)
- Cosmos DB (metadatos de configuración SharePoint)
- Blob Storage (fuente/logs/imágenes)

Campos típicos indexados por chunk:
- `id`, `parent_id`, `content`, `contentVector`, `captionVector`, `source`, `metadata_storage_last_modified`, `relatedImages`, `userIds/groupIds/rbacScope` (según configuración ACL).

### 5.6 Modos de despliegue comparados

| Modo | Comando principal | Cuándo usar | Ventaja | Limitación |
|---|---|---|---|---|
| Deploy app sobre infra existente | `azd env refresh` + `azd deploy` | Camino recomendado en este repo | Reutiliza plataforma GPT-RAG | No provisiona infra aquí |
| Script bash | `scripts/deploy.sh` | CI/CD Linux/macOS o local | Automatiza build/push/update Container App | Requiere App Config keys correctas |
| Script PowerShell | `scripts/deploy.ps1` | Entornos Windows | Flujo equivalente con validaciones | Mismas dependencias Azure/Docker |
| Build remoto ACR | `az acr build` | Sin Docker local estable | Evita dependencia local Docker daemon | Más lento según red/build queue |

### 5.7 Modelo de seguridad
- **Autenticación de servicio a servicio**: Entra ID con Managed Identity / Azure CLI creds.
- **Autorización**:
  - RBAC Azure por recurso (Storage/Search/KeyVault/AppConfig/etc.)
  - Validación de `X-API-KEY` para endpoints de skill.
- **SharePoint**:
  - App registration + secret en Key Vault para Graph.
- **RBAC documental (feature v2.2.0+)**:
  - Indexación de metadata de permisos (`userIds`, `groupIds`, `rbacScope`) para trimming en consulta.

---

## 6. Fuera de Alcance

| Gap nativo | Descripción | Esfuerzo estimado | Librerías/servicios sugeridos |
|---|---|---|---|
| UI de operación | No incluye dashboard web para monitoreo/reprocesamiento | Medio | React + FastAPI admin endpoints + App Insights API |
| Orquestación de workflows complejos | No hay engine tipo DAG con dependencias declarativas | Medio-Alto | Durable Functions, Prefect, Airflow |
| CDC transaccional RDBMS | No consume cambios vía log-based CDC | Alto | Debezium, ADF, Fabric pipelines |
| Gestión de esquemas de índices | No incluye IaC detallado de todos índices/campos | Medio | Terraform/Bicep para Search index definitions |
| Test suite automatizada robusta | No se observa carpeta de tests en el repo | Medio | pytest + pytest-asyncio + fixtures de Azure SDK |
| Multi-tenant hard isolation | No incluye particionamiento completo por tenant en runtime | Alto | Aislamiento por índice/container/MI por tenant |
| Backpressure centralizado | Retries existen, pero sin controlador global de throughput cross-job | Medio | leaky-bucket/queue (Redis, Service Bus) |
| Data lineage formal | No hay grafo de lineage completo por chunk->origen->run | Medio | OpenLineage + metadata store |

---

## 7. Escenarios de Ejemplo

> Los siguientes ejemplos son patrones funcionales basados en la API/arquitectura de este repositorio. Se muestran en YAML/Python para servir como plantillas de implementación.

### 7.1 Finanzas: contratos PDF + extracción multimodal
```yaml
scenario: finanzas-contratos
source:
  type: blob
  container: documents
  prefix: finance/contracts/
pipeline:
  - step: discover
    worker: blob-storage-indexer
  - step: chunk
    mode: multimodal
    settings:
      MULTIMODAL: "true"
      CHUNKING_NUM_TOKENS: 2048
  - step: index
    target_index: ragindex-finance
```

### 7.2 Salud: políticas médicas DOCX con privacidad
```yaml
scenario: salud-politicas
source:
  type: sharepoint
  site: health-policies
security:
  acl_trimming: true
pipeline:
  - sharepoint-indexer
  - document_chunking
  - ai_search_upsert
```

### 7.3 Legal: repositorio jurisprudencia en SharePoint
```python
# Trigger manual para reprocesar una lista legal específica
from jobs.sharepoint_indexer import SharePointIndexer

async def run_legal_reindex():
    await SharePointIndexer().run()
```

### 7.4 Manufactura: manuales técnicos + imágenes
```yaml
scenario: manufactura-manuales
source:
  type: blob
  file_types: [pdf, png, jpg]
pipeline:
  - blob-storage-indexer
  - multimodal-chunker
  - multimodal-images-purger
```

### 7.5 Retail: NL2SQL para analítica de ventas
```yaml
scenario: retail-nl2sql
source:
  type: blob
  container: nl2sql
  folders: [queries/, tables/, measures/]
pipeline:
  - nl2sql-indexer
  - nl2sql-purger
indices:
  - SEARCH_QUERIES_INDEX_NAME
  - SEARCH_TABLES_INDEX_NAME
  - SEARCH_MEASURES_INDEX_NAME
```

### 7.6 Contact center: transcripciones VTT
```python
payload = {
    "values": [{
        "recordId": "1",
        "data": {
            "documentUrl": "https://<storage>/documents/contact-center/contact-center-long.vtt",
            "documentContentType": "text/vtt"
        }
    }]
}
# POST /document-chunking
```

### 7.7 Pipeline paralelo: Blob + SharePoint simultáneo
```yaml
scenario: paralelo-blob-sharepoint
parallel:
  - worker: blob-storage-indexer
  - worker: sharepoint-indexer
join:
  - step: consistency-purge
    workers: [blob-storage-indexer-purger, sharepoint-purger]
```

### 7.8 Pipeline condicional por tipo de archivo
```yaml
scenario: condicional-por-extension
rules:
  - if: extension in ["xlsx", "xls"]
    then: SpreadsheetChunker
  - if: extension in ["pdf", "png", "jpg"] and MULTIMODAL=true
    then: MultimodalChunker
  - else: LangChainChunker
```

### 7.9 Multi-etapa: índice legal con hardening
```yaml
scenario: multi-stage-legal
stages:
  - ingest:
      worker: sharepoint-indexer
  - enrich:
      steps: [document_chunking, text_embedding]
  - secure:
      acl: true
      rbac_scope: legal
  - maintain:
      crons:
        purge: "0 3 * * *"
        reindex: "0 */6 * * *"
```

### 7.10 Seguros: lote nocturno con fallback y retries
```python
import asyncio
from jobs.blob_storage_indexer import BlobStorageDocumentIndexer
from jobs.nl2sql_indexer import NL2SQLIndexer

async def nightly_batch():
    await asyncio.gather(
        BlobStorageDocumentIndexer().run(),
        NL2SQLIndexer().run(),
    )
```

---

## 8. Índice de Samples Incluidos

### 8.1 Documentos generales

| Sample | Descripción | Ruta |
|---|---|---|
| Contact center long | Transcripción larga en VTT | `samples/documents/contact-center/contact-center-long.vtt` |
| Contact center short | Transcripción corta en VTT | `samples/documents/contact-center/contact-center-short.vtt` |
| Benefit Options | PDF de beneficios (contoso) | `samples/documents/contoso-eletronics/Benefit_Options.pdf` |
| Northwind Health Plus | PDF de beneficios | `samples/documents/contoso-eletronics/Northwind_Health_Plus_Benefits_Details.pdf` |
| Northwind Standard | PDF de beneficios | `samples/documents/contoso-eletronics/Northwind_Standard_Benefits_Details.pdf` |
| Employee handbook | Manual PDF corporativo | `samples/documents/contoso-eletronics/employee_handbook.pdf` |
| Modem manual | Manual en Markdown | `samples/documents/manuals/modem-manual.md` |
| Surface Pro guide | Manual PDF técnico | `samples/documents/manuals/surface-pro-4-user-guide-EN.pdf` |
| Spreadsheet sample | Libro Excel de ejemplo | `samples/documents/spreadsheets/sample-workbook.xlsx` |

### 8.2 NL2SQL — SQL Database

| Tipo | Nombre | Ruta |
|---|---|---|
| Datasource | AdventureWorks datasource | `samples/sql_database/datasources.json` |
| Query | Query 1 | `samples/sql_database/queries/adventureworks_query_1.json` |
| Query | Query 2 | `samples/sql_database/queries/adventureworks_query_2.json` |
| Query | Query 3 | `samples/sql_database/queries/adventureworks_query_3.json` |
| Query | Query 4 | `samples/sql_database/queries/adventureworks_query_4.json` |
| Query | Query 5 | `samples/sql_database/queries/adventureworks_query_5.json` |
| Table | SalesLT.Address | `samples/sql_database/tables/adventureworks-saleslt_address.json` |
| Table | SalesLT.Customer | `samples/sql_database/tables/adventureworks-saleslt_customer.json` |
| Table | SalesLT.Product | `samples/sql_database/tables/adventureworks-saleslt_product.json` |
| Table | SalesLT.ProductCategory | `samples/sql_database/tables/adventureworks-saleslt_productcategory.json` |
| Table | SalesLT.ProductDescription | `samples/sql_database/tables/adventureworks-saleslt_productdescription.json` |
| Table | SalesLT.ProductModel | `samples/sql_database/tables/adventureworks-saleslt_productmodel.json` |
| Table | SalesLT.SalesOrderDetail | `samples/sql_database/tables/adventureworks-saleslt_salesorderdetail.json` |
| Table | SalesLT.SalesOrderHeader | `samples/sql_database/tables/adventureworks-saleslt_salesorderheader.json` |

### 8.3 NL2SQL — Microsoft Fabric

| Tipo | Nombre | Ruta |
|---|---|---|
| Datasource | Fabric datasources | `samples/fabric/datasources.json` |
| Query | Aggregate query 1 | `samples/fabric/queries/wwi_sales_aggregate_data_query_1.json` |
| Query | Aggregate query 2 | `samples/fabric/queries/wwi_sales_aggregate_data_query_2.json` |
| Query | Aggregate query 3 | `samples/fabric/queries/wwi_sales_aggregate_data_query_3.json` |
| Table | aggregate_sale_by_date_city | `samples/fabric/tables/wwi_sales_aggregated_data-aggregate_sale_by_date_city.json` |
| Table | aggregate_sale_by_date_employee | `samples/fabric/tables/wwi_sales_aggregated_data-aggregate_sale_by_date_employee_.json` |
| Table | dimension_city | `samples/fabric/tables/wwi_sales_star_schema-dimension_city.json` |
| Table | dimension_customer | `samples/fabric/tables/wwi_sales_star_schema-dimension_customer.json` |
| Table | dimension_date | `samples/fabric/tables/wwi_sales_star_schema-dimension_date.json` |
| Table | dimension_employee | `samples/fabric/tables/wwi_sales_star_schema-dimension_employee.json` |
| Table | dimension_stock_item | `samples/fabric/tables/wwi_sales_star_schema-dimension_stock_item.json` |
| Table | fact_sale | `samples/fabric/tables/wwi_sales_star_schema-fact_sale.json` |

---

## 9. Soporte de Despliegue con IaC (Infrastructure as Code)

### 9.1 ¿Incluye IaC?
Sí, incluye artefactos de IaC **mínimos** para acoplarse a una infraestructura externa del proyecto padre GPT-RAG.

### 9.2 Archivos IaC encontrados

| Archivo | Tipo | Propósito |
|---|---|---|
| `azure.yaml` | Descriptor `azd` | Define proyecto, provider `bicep`, hooks preprovision/predeploy |
| `infra/main.bicep` | Bicep | Stub de alcance `resourceGroup` (sin recursos definidos en este repo) |
| `infra/README.md` | Documentación IaC | Declara que la infraestructura vive en repo externo `Azure/GPT-RAG` |

### 9.3 Recursos aprovisionados por cada archivo
- `infra/main.bicep`: actualmente no aprovisiona recursos (solo `targetScope`).
- `azure.yaml`: no crea recursos por sí mismo; orquesta hooks/scripts y despliegue de aplicación.

### 9.4 Cobertura de IaC
Cobertura **parcial** en este repositorio: despliegue de aplicación sí, plataforma completa no.

### 9.5 Gaps (recursos manuales/externos)
Se deben crear/proveer externamente (normalmente desde repo raíz GPT-RAG):
- Azure Container Apps environment y Container App objetivo.
- ACR y login server.
- Azure App Configuration con claves requeridas.
- Storage account + containers (`documents`, `jobs`, `documents-images`, `nl2sql`, etc.).
- AI Search + índices (RAG y NL2SQL).
- OpenAI/Foundry deployments.
- Key Vault + secretos.
- Cosmos DB y contenedores de configuración.
- Recursos de observabilidad.

### 9.6 Flujo de despliegue paso a paso
1. Provisionar infraestructura completa en el proyecto padre GPT-RAG.
2. En este repo, ejecutar `azd env refresh` con mismo env/subscription/location.
3. Ejecutar `azd deploy` para desplegar la aplicación.
4. Alternativa: usar `scripts/deploy.sh` o `scripts/deploy.ps1` para build/push/update de Container App.
5. Validar health endpoints (`/healthz`, `/readyz`) y cron jobs.

**Nota importante:** `scripts/preProvision.*` bloquean explícitamente `azd provision`/`azd up` en este repositorio.

### 9.7 Múltiples entornos
- Soportado mediante entornos `azd` y valores de App Configuration por label.
- Parametrización operativa por variables y keys (`APP_CONFIG_ENDPOINT`, nombres de recursos, cron settings).
- Estrategia recomendada: `dev/staging/prod` en infra padre + `azd env` separados.

### 9.8 Herramientas de despliegue requeridas

| Herramienta | Uso | Mínimo sugerido |
|---|---|---|
| Azure CLI | Login, ACR build/push, update container app | 2.57+ |
| Azure Developer CLI (`azd`) | Refresh/deploy del servicio | 1.10+ |
| Docker (opcional) | Build local de imagen | 24+ |
| Git | Tag basado en commit | 2.40+ |

### 9.9 Evaluación de madurez IaC

| Criterio | Estado | Notas |
|---|---|---|
| Archivos IaC presentes | ✅ | `azure.yaml` + `infra/main.bicep` + scripts |
| Cobertura completa de recursos | ⚠️ | Infra completa delegada a repo externo GPT-RAG |
| Parametrización por entorno | ✅ | Basada en `azd env` + App Config |
| Integración CI/CD | ⚠️ | Scripts de despliegue listos; pipeline CI/CD no definido en este repo |
| Documentación de despliegue | ⚠️ | README mínimo; depende de documentación externa |
| Idempotencia (re-ejecutable) | ✅ | `azd deploy` y scripts de update son re-ejecutables (con infra previa) |

---

## Apéndice A — Inventario de archivos clave analizados

- Documentación y metadatos: `README.md`, `CHANGELOG.md`, `LICENSE.md`, `VERSION`.
- Runtime/API: `main.py`, `dependencies.py`, `constants.py`.
- Chunking: `chunking/` completo.
- Jobs: `jobs/` completo.
- Integraciones: `tools/` completo.
- Utilidades/telemetría: `utils/`, `telemetry/`.
- Infra/despliegue: `azure.yaml`, `infra/*`, `scripts/*`, `Dockerfile`, `launch.json`, `requirements.txt`.
- Samples: `samples/` completo (documentos, fabric, sql_database).
