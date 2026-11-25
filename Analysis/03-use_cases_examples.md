# 03-use_cases_examples — Catálogo de Casos de Uso Implementables (GPT-RAG Data Ingestion)

## Tabla de contenidos
- [1. Criterios de Selección de Casos de Uso](#1-criterios-de-selección-de-casos-de-uso)
- [2. Catálogo de Casos de Uso](#2-catálogo-de-casos-de-uso)
  - [Caso 1: Manuales de productos para FAQ interno](#caso-1-manuales-de-productos-para-faq-interno)
  - [Caso 2: Transcripciones de contact center para búsqueda semántica](#caso-2-transcripciones-de-contact-center-para-búsqueda-semántica)
  - [Caso 3: Facturas y formularios financieros (documentos estructurados)](#caso-3-facturas-y-formularios-financieros-documentos-estructurados)
  - [Caso 4: Contratos legales con anexos e imágenes (multimodal)](#caso-4-contratos-legales-con-anexos-e-imágenes-multimodal)
  - [Caso 5: Historias clínicas y pólizas médicas con enrutamiento condicional](#caso-5-historias-clínicas-y-pólizas-médicas-con-enrutamiento-condicional)
  - [Caso 6: Reportes tabulares de manufactura (extracción numérica)](#caso-6-reportes-tabulares-de-manufactura-extracción-numérica)
  - [Caso 7: Ingesta documental empresarial desde SharePoint](#caso-7-ingesta-documental-empresarial-desde-sharepoint)
  - [Caso 8: Procesamiento masivo nocturno por lotes (batch)](#caso-8-procesamiento-masivo-nocturno-por-lotes-batch)
  - [Caso 9: Fan-out/Fan-in híbrido Blob + SharePoint](#caso-9-fan-outfan-in-híbrido-blob--sharepoint)
  - [Caso 10: Índices NL2SQL para analítica en retail/BI](#caso-10-índices-nl2sql-para-analítica-en-retailbi)
  - [Caso 11: Web scraping + RAG documental (extensión implementable)](#caso-11-web-scraping--rag-documental-extensión-implementable)
  - [Caso 12: Grafo de conocimiento y comparación multi-documento (extensión implementable)](#caso-12-grafo-de-conocimiento-y-comparación-multi-documento-extensión-implementable)
- [3. Tabla Resumen de Componentes por Caso de Uso](#3-tabla-resumen-de-componentes-por-caso-de-uso)
- [4. Índice de Samples Oficiales Incluidos en el Repositorio](#4-índice-de-samples-oficiales-incluidos-en-el-repositorio)
- [5. Combinaciones de Componentes Recomendadas](#5-combinaciones-de-componentes-recomendadas)

---

## 1. Criterios de Selección de Casos de Uso

### 1.1 Qué tipos de problemas puede resolver este proyecto
GPT-RAG Data Ingestion resuelve principalmente problemas de:
- Ingesta de contenido empresarial heterogéneo (PDF, Office, imágenes, markdown, VTT, JSON, Excel).
- Preparación de datos para RAG en Azure AI Search con embeddings.
- Indexación incremental y purga de datos obsoletos.
- Ingestión desde fuentes operativas comunes (Blob Storage y SharePoint).
- Construcción de índices de conocimiento estructurado para NL2SQL (queries, tablas, medidas).

### 1.2 Mapeo de caso de negocio -> componentes del proyecto
Regla práctica de mapeo:
1. Definir fuente: Blob (`blob-storage-indexer`) o SharePoint (`sharepoint-indexer`) o NL2SQL (`nl2sql-indexer`).
2. Definir tipo de contenido: `ChunkerFactory` enruta a `DocAnalysisChunker`, `MultimodalChunker`, `SpreadsheetChunker`, `TranscriptionChunker`, `JSONChunker`, `LangChainChunker`, `NL2SQLChunker`.
3. Definir objetivo de consulta: índice RAG general o índices NL2SQL especializados.
4. Definir mantenimiento: purga (`blob-storage-indexer-purger`, `sharepoint-purger`, `nl2sql-indexer-purger`, `multimodality-images-purger`).
5. Definir modo operativo: HTTP on-demand (`document-chunking`, `text-embedding`) o batch por cron (APScheduler).

### 1.3 IDs de componentes/executors usados en este documento
IDs exactos usados en código del repositorio:
- `document-chunking`
- `text-embedding`
- `blob-storage-indexer`
- `blob-storage-indexer-purger`
- `sharepoint-indexer`
- `sharepoint-purger`
- `nl2sql-indexer`
- `nl2sql-indexer-purger`
- `multimodality-images-purger`
- Chunkers referenciados por nombre de clase: `DocAnalysisChunker`, `MultimodalChunker`, `SpreadsheetChunker`, `TranscriptionChunker`, `JSONChunker`, `LangChainChunker`, `NL2SQLChunker`

---

## 2. Catálogo de Casos de Uso

### Caso 1: Manuales de productos para FAQ interno
**Sector/Industria:** Retail / Soporte técnico  
**Descripción del problema:** El equipo de soporte necesita responder preguntas sobre manuales técnicos en segundos.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Cargar manuales PDF/MD en Blob.
2. Ejecutar `blob-storage-indexer` para chunking automático.
3. Publicar chunks en índice RAG.
4. Programar purga para mantener consistencia.

**Componentes utilizados:** `blob-storage-indexer`, `blob-storage-indexer-purger`, `DocAnalysisChunker`, `LangChainChunker`, `document-chunking`, `text-embedding`

**Pipeline YAML completo**
```yaml
name: retail-faq-manuales
source:
  kind: blob
  container: documents
  prefix: manuals/
executors:
  - id: blob-storage-indexer
    schedule: "0 */2 * * *"
    config:
      BLOB_PREFIX: "manuals/"
      MULTIMODAL: "false"
  - id: blob-storage-indexer-purger
    schedule: "15 */2 * * *"
api:
  chunking_endpoint: document-chunking
  embedding_endpoint: text-embedding
output:
  ai_search_index: ragindex-retail
```

**Notas de implementación:**
- Ideal para contenidos no visuales complejos.
- Si predominan tablas o diagramas, activar caso multimodal.

---

### Caso 2: Transcripciones de contact center para búsqueda semántica
**Sector/Industria:** Telecom / BPO  
**Descripción del problema:** Hallar conversaciones relevantes por tema en miles de llamadas.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Subir `.vtt` al contenedor de documentos.
2. `ChunkerFactory` enruta a `TranscriptionChunker`.
3. Se generan chunks con resumen de conversación.
4. Se indexa para búsqueda semántica.

**Componentes utilizados:** `blob-storage-indexer`, `TranscriptionChunker`, `text-embedding`

**Pipeline YAML completo**
```yaml
name: contact-center-vtt
source:
  kind: blob
  container: documents
  prefix: contact-center/
executors:
  - id: blob-storage-indexer
    schedule: "0 * * * *"
    config:
      BLOB_PREFIX: "contact-center/"
      CHUNKING_NUM_TOKENS: "2048"
      TOKEN_OVERLAP: "100"
routing:
  vtt: TranscriptionChunker
output:
  ai_search_index: ragindex-contactcenter
```

**Notas de implementación:**
- Recomendado combinar con metadata de agente/campaña para mejores filtros.

---

### Caso 3: Facturas y formularios financieros (documentos estructurados)
**Sector/Industria:** Finanzas  
**Descripción del problema:** Indexar facturas y formularios para auditoría y consulta rápida.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Ingestar PDF de facturas en Blob.
2. Procesar con `DocAnalysisChunker` (OCR/layout).
3. Generar embeddings e indexar.
4. Ejecutar purga incremental.

**Componentes utilizados:** `blob-storage-indexer`, `DocAnalysisChunker`, `document-chunking`, `blob-storage-indexer-purger`

**Pipeline YAML completo**
```yaml
name: finanzas-facturas
source:
  kind: blob
  container: documents
  prefix: finance/invoices/
executors:
  - id: blob-storage-indexer
    schedule: "0 1 * * *"
    config:
      BLOB_PREFIX: "finance/invoices/"
      MULTIMODAL: "false"
      DOC_INTELLIGENCE_API_VERSION: "2024-11-30"
  - id: blob-storage-indexer-purger
    schedule: "30 1 * * *"
routing:
  pdf: DocAnalysisChunker
output:
  ai_search_index: ragindex-finance
```

**Notas de implementación:**
- Para extraer campos contables normalizados se recomienda post-proceso adicional.

---

### Caso 4: Contratos legales con anexos e imágenes (multimodal)
**Sector/Industria:** Legal  
**Descripción del problema:** Contratos con tablas escaneadas y anexos visuales difíciles de consultar.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Activar `MULTIMODAL=true`.
2. Ingerir PDF/imagenes.
3. `MultimodalChunker` genera `relatedImages` + captions vectorizadas.
4. Purgar imágenes huérfanas automáticamente.

**Componentes utilizados:** `blob-storage-indexer`, `multimodality-images-purger`, `MultimodalChunker`

**Pipeline YAML completo**
```yaml
name: legal-contratos-multimodal
source:
  kind: blob
  container: documents
  prefix: legal/contracts/
executors:
  - id: blob-storage-indexer
    schedule: "0 */4 * * *"
    config:
      BLOB_PREFIX: "legal/contracts/"
      MULTIMODAL: "true"
      DOCUMENTS_IMAGES_STORAGE_CONTAINER: "documents-images"
      MINIMUM_FIGURE_AREA_PERCENTAGE: "4.0"
  - id: multimodality-images-purger
    schedule: "20 */4 * * *"
routing:
  pdf: MultimodalChunker
  png: MultimodalChunker
  jpg: MultimodalChunker
output:
  ai_search_index: ragindex-legal
```

**Notas de implementación:**
- Elevar `MINIMUM_FIGURE_AREA_PERCENTAGE` reduce ruido de imágenes pequeñas.

---

### Caso 5: Historias clínicas y pólizas médicas con enrutamiento condicional
**Sector/Industria:** Salud  
**Descripción del problema:** Mezcla de PDFs clínicos, hojas de cálculo de laboratorio y JSON operativos.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Unificar carga en Blob.
2. Enrutar por extensión con `ChunkerFactory`.
3. Aplicar chunker especializado por tipo.
4. Indexar con metadata clínica por source/category.

**Componentes utilizados:** `blob-storage-indexer`, `DocAnalysisChunker`, `SpreadsheetChunker`, `JSONChunker`, `LangChainChunker`

**Pipeline YAML completo**
```yaml
name: salud-routing-condicional
source:
  kind: blob
  container: documents
  prefix: health/
executors:
  - id: blob-storage-indexer
    schedule: "0 */3 * * *"
    config:
      BLOB_PREFIX: "health/"
      SPREADSHEET_CHUNKING_BY_ROW: "true"
      SPREADSHEET_CHUNKING_BY_ROW_INCLUDE_HEADER: "true"
routing:
  pdf: DocAnalysisChunker
  docx: DocAnalysisChunker
  xlsx: SpreadsheetChunker
  xls: SpreadsheetChunker
  json: JSONChunker
  md: LangChainChunker
output:
  ai_search_index: ragindex-health
```

**Notas de implementación:**
- Agregar políticas de redacción/PII downstream antes de habilitar consumo amplio.

---

### Caso 6: Reportes tabulares de manufactura (extracción numérica)
**Sector/Industria:** Manufactura  
**Descripción del problema:** Buscar KPIs y anomalías en reportes Excel extensos.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Activar chunking por fila para granularidad numérica.
2. Embedding por texto compacto de fila.
3. Indexar resultados para consultas de métricas.

**Componentes utilizados:** `blob-storage-indexer`, `SpreadsheetChunker`, `text-embedding`

**Pipeline YAML completo**
```yaml
name: manufactura-spreadsheets
source:
  kind: blob
  container: documents
  prefix: plant/reports/
executors:
  - id: blob-storage-indexer
    schedule: "0 2 * * *"
    config:
      BLOB_PREFIX: "plant/reports/"
      SPREADSHEET_CHUNKING_BY_ROW: "true"
      SPREADSHEET_CHUNKING_BY_ROW_INCLUDE_HEADER: "true"
      SPREADSHEET_CHUNKING_NUM_TOKENS: "1200"
routing:
  xlsx: SpreadsheetChunker
  xls: SpreadsheetChunker
output:
  ai_search_index: ragindex-manufacturing
```

**Notas de implementación:**
- Muy útil para preguntas agregadas por línea/planta/periodo.

---

### Caso 7: Ingesta documental empresarial desde SharePoint
**Sector/Industria:** Corporativo transversal  
**Descripción del problema:** Documentación distribuida en listas y bibliotecas SharePoint.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Configurar sites/lists en Cosmos (`datasources`).
2. Ejecutar `sharepoint-indexer` para descubrir, descargar y chunkear.
3. Usar `sharepoint-purger` para sincronizar eliminaciones.

**Componentes utilizados:** `sharepoint-indexer`, `sharepoint-purger`, `SharePointGraphClient`, `CosmosDBClient`, `DocAnalysisChunker`, `LangChainChunker`

**Pipeline YAML completo**
```yaml
name: sharepoint-enterprise
source:
  kind: sharepoint
  config_store: cosmosdb
executors:
  - id: sharepoint-indexer
    schedule: "0 */6 * * *"
    config:
      SP_INDEXER_NAME: "sharepoint-indexer"
      INDEXER_MAX_CONCURRENCY: "4"
      SHAREPOINT_FILES_FORMAT: "pdf,docx,pptx"
  - id: sharepoint-purger
    schedule: "30 */6 * * *"
security:
  acl_rbac_trimming: true
output:
  ai_search_index: ragindex-enterprise
```

**Notas de implementación:**
- Requiere permisos Graph y secreto de app en Key Vault.

---

### Caso 8: Procesamiento masivo nocturno por lotes (batch)
**Sector/Industria:** Seguros / Banca  
**Descripción del problema:** Ventana nocturna para millones de páginas y limpieza diaria.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Incrementar concurrencia y batch size.
2. Programar index y purge en secuencia nocturna.
3. Usar logs por ejecución para auditoría.

**Componentes utilizados:** `blob-storage-indexer`, `blob-storage-indexer-purger`, `document-chunking`, `text-embedding`

**Pipeline YAML completo**
```yaml
name: batch-nocturno-masivo
source:
  kind: blob
  container: documents
  prefix: nightly/
executors:
  - id: blob-storage-indexer
    schedule: "0 0 * * *"
    config:
      BLOB_PREFIX: "nightly/"
      INDEXER_MAX_CONCURRENCY: "12"
      INDEXER_BATCH_SIZE: "500"
      OPENAI_RETRY_MAX_ATTEMPTS: "20"
  - id: blob-storage-indexer-purger
    schedule: "0 3 * * *"
observability:
  run_logs_container: jobs
output:
  ai_search_index: ragindex-batch
```

**Notas de implementación:**
- Ajustar TPM de embeddings para evitar cuellos de botella.

---

### Caso 9: Fan-out/Fan-in híbrido Blob + SharePoint
**Sector/Industria:** Legal / Compliance global  
**Descripción del problema:** Consolidar evidencia de múltiples repositorios en un índice único.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Fan-out: correr indexación Blob y SharePoint en paralelo.
2. Fan-in: ejecutar purgers para convergencia de estado.
3. Mantener trazabilidad por `runId`.

**Componentes utilizados:** `blob-storage-indexer`, `sharepoint-indexer`, `blob-storage-indexer-purger`, `sharepoint-purger`

**Pipeline YAML completo**
```yaml
name: fanout-fanin-hibrido
parallel:
  - id: blob-storage-indexer
    schedule: "0 */8 * * *"
    config:
      BLOB_PREFIX: "compliance/"
  - id: sharepoint-indexer
    schedule: "0 */8 * * *"
fan_in:
  - id: blob-storage-indexer-purger
    schedule: "45 */8 * * *"
  - id: sharepoint-purger
    schedule: "50 */8 * * *"
output:
  ai_search_index: ragindex-compliance
```

**Notas de implementación:**
- Patrón robusto para organizaciones con fuentes duplicadas o superpuestas.

---

### Caso 10: Índices NL2SQL para analítica en retail/BI
**Sector/Industria:** Retail / Analytics  
**Descripción del problema:** Transformar preguntas de negocio en consultas SQL/DAX recuperables semánticamente.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Cargar `datasources/queries/tables` en contenedor `nl2sql`.
2. Ejecutar `nl2sql-indexer` para poblar índices especializados.
3. Ejecutar `nl2sql-indexer-purger` para eliminar huérfanos.

**Componentes utilizados:** `nl2sql-indexer`, `nl2sql-indexer-purger`, `NL2SQLChunker`, `text-embedding`

**Pipeline YAML completo**
```yaml
name: nl2sql-retail-bi
source:
  kind: blob
  container: nl2sql
  folders: [queries/, tables/, measures/]
executors:
  - id: nl2sql-indexer
    schedule: "0 */4 * * *"
    config:
      NL2SQL_STORAGE_CONTAINER: "nl2sql"
      SEARCH_QUERIES_INDEX_NAME: "queries-index"
      SEARCH_TABLES_INDEX_NAME: "tables-index"
      SEARCH_MEASURES_INDEX_NAME: "measures-index"
  - id: nl2sql-indexer-purger
    schedule: "15 */4 * * *"
output:
  ai_search_indexes:
    - queries-index
    - tables-index
    - measures-index
```

**Notas de implementación:**
- Soporta samples de `samples/sql_database` y `samples/fabric`.

---

### Caso 11: Web scraping + RAG documental (extensión implementable)
**Sector/Industria:** Medios / Inteligencia competitiva  
**Descripción del problema:** Indexar contenido web público actualizado para asistentes internos.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Scraper externo descarga HTML/MD y publica en Blob.
2. Ingesta estándar con `blob-storage-indexer`.
3. Chunking por `LangChainChunker` para contenido web textual.

**Componentes utilizados:** `blob-storage-indexer`, `blob-storage-indexer-purger`, `LangChainChunker` (+ scraper externo previo)

**Pipeline YAML completo**
```yaml
name: web-scraping-rag
pre_stage:
  external_collector:
    output_container: documents
    output_prefix: web/
executors:
  - id: blob-storage-indexer
    schedule: "0 */2 * * *"
    config:
      BLOB_PREFIX: "web/"
  - id: blob-storage-indexer-purger
    schedule: "20 */2 * * *"
routing:
  html: LangChainChunker
  htm: LangChainChunker
  md: LangChainChunker
output:
  ai_search_index: ragindex-web
```

**Notas de implementación:**
- El scraping no es nativo del repo; se integra como pre-etapa upstream.

---

### Caso 12: Grafo de conocimiento y comparación multi-documento (extensión implementable)
**Sector/Industria:** Farma / Legal / Investigación  
**Descripción del problema:** Comparar lotes documentales y derivar entidades/relaciones para análisis avanzado.  
**Solución con GPT-RAG Data Ingestion (paso a paso):**
1. Ingerir fuentes múltiples (Blob + SharePoint).
2. Indexar con metadatos consistentes por `parent_id`, `source`, `filepath`.
3. Ejecutar post-proceso externo que consume AI Search y construye grafo.

**Componentes utilizados:** `blob-storage-indexer`, `sharepoint-indexer`, `document-chunking`, `text-embedding`, `sharepoint-purger`, `blob-storage-indexer-purger` (+ constructor de grafo externo)

**Pipeline YAML completo**
```yaml
name: knowledge-graph-multidoc
parallel:
  - id: blob-storage-indexer
    schedule: "0 */12 * * *"
    config:
      BLOB_PREFIX: "research/"
  - id: sharepoint-indexer
    schedule: "0 */12 * * *"
fan_in:
  - id: sharepoint-purger
    schedule: "40 */12 * * *"
  - id: blob-storage-indexer-purger
    schedule: "45 */12 * * *"
post_stage:
  external_graph_builder:
    input: ai_search_index
    output: knowledge_graph_store
output:
  ai_search_index: ragindex-research
```

**Notas de implementación:**
- La construcción de grafo no es nativa; este repositorio cubre ingesta, chunking y embeddings.

---

## 3. Tabla Resumen de Componentes por Caso de Uso

| Caso de Uso | Componentes Requeridos | Servicios Azure | Complejidad |
|---|---|---|---|
| Manuales para FAQ | `blob-storage-indexer`, `blob-storage-indexer-purger`, `DocAnalysisChunker`, `LangChainChunker` | Blob, AI Search, OpenAI, App Config | Baja |
| Transcripciones contact center | `blob-storage-indexer`, `TranscriptionChunker` | Blob, AI Search, OpenAI | Baja |
| Facturas/formularios | `blob-storage-indexer`, `DocAnalysisChunker`, `blob-storage-indexer-purger` | Blob, AI Search, Document Intelligence, OpenAI | Baja-Media |
| Contratos multimodales | `blob-storage-indexer`, `MultimodalChunker`, `multimodality-images-purger` | Blob, AI Search, Document Intelligence, OpenAI | Media |
| Salud condicional | `blob-storage-indexer`, `DocAnalysisChunker`, `SpreadsheetChunker`, `JSONChunker`, `LangChainChunker` | Blob, AI Search, OpenAI, Document Intelligence | Media |
| Manufactura tabular | `blob-storage-indexer`, `SpreadsheetChunker` | Blob, AI Search, OpenAI | Media |
| SharePoint empresarial | `sharepoint-indexer`, `sharepoint-purger` | Graph, Key Vault, Cosmos DB, AI Search, Blob | Media-Alta |
| Batch nocturno masivo | `blob-storage-indexer`, `blob-storage-indexer-purger` | Blob, AI Search, OpenAI, App Insights | Alta |
| Fan-out/Fan-in híbrido | `blob-storage-indexer`, `sharepoint-indexer`, purgers | Blob, Graph, AI Search, Cosmos, Key Vault | Alta |
| NL2SQL BI | `nl2sql-indexer`, `nl2sql-indexer-purger`, `NL2SQLChunker` | Blob, AI Search (3 índices), OpenAI | Alta |
| Web scraping + RAG | `blob-storage-indexer`, `LangChainChunker` (+ externo) | Blob, AI Search, OpenAI | Alta |
| Grafo + multi-documento | Indexers/purgers + `document-chunking` (+ externo) | Blob, SharePoint/Graph, AI Search, OpenAI | Muy Alta |

---

## 4. Índice de Samples Oficiales Incluidos en el Repositorio

### 4.1 Samples de documentos

| # | Directorio/archivo | Descripción (1 oración) | Componentes que demuestra | Ruta relativa |
|---|---|---|---|---|
| 1 | contact-center-long.vtt | Transcripción larga para chunking conversacional. | `TranscriptionChunker`, `document-chunking` | `samples/documents/contact-center/contact-center-long.vtt` |
| 2 | contact-center-short.vtt | Transcripción corta de prueba para validación rápida. | `TranscriptionChunker` | `samples/documents/contact-center/contact-center-short.vtt` |
| 3 | Benefit_Options.pdf | PDF corporativo de beneficios para OCR/chunking documental. | `DocAnalysisChunker` | `samples/documents/contoso-eletronics/Benefit_Options.pdf` |
| 4 | Northwind_Health_Plus_Benefits_Details.pdf | Documento de pólizas útil para escenarios de salud. | `DocAnalysisChunker` | `samples/documents/contoso-eletronics/Northwind_Health_Plus_Benefits_Details.pdf` |
| 5 | Northwind_Standard_Benefits_Details.pdf | Variante de póliza para comparación de contenido. | `DocAnalysisChunker`, comparación multi-doc | `samples/documents/contoso-eletronics/Northwind_Standard_Benefits_Details.pdf` |
| 6 | employee_handbook.pdf | Manual organizacional no estructurado. | `DocAnalysisChunker`, RAG base | `samples/documents/contoso-eletronics/employee_handbook.pdf` |
| 7 | modem-manual.md | Documento markdown técnico para split semántico textual. | `LangChainChunker` | `samples/documents/manuals/modem-manual.md` |
| 8 | surface-pro-4-user-guide-EN.pdf | Manual técnico de producto en PDF. | `DocAnalysisChunker` | `samples/documents/manuals/surface-pro-4-user-guide-EN.pdf` |
| 9 | sample-workbook.xlsx | Libro Excel para chunking por hoja/fila y datos numéricos. | `SpreadsheetChunker` | `samples/documents/spreadsheets/sample-workbook.xlsx` |

### 4.2 Samples NL2SQL (SQL Database)

| # | Directorio/archivo | Descripción (1 oración) | Componentes que demuestra | Ruta relativa |
|---|---|---|---|---|
| 10 | datasources.json | Define datasource AdventureWorks para NL2SQL. | `nl2sql-indexer` | `samples/sql_database/datasources.json` |
| 11 | adventureworks_query_1.json | Ejemplo de pregunta SQL de ranking de productos. | `nl2sql-indexer`, `NL2SQLChunker` | `samples/sql_database/queries/adventureworks_query_1.json` |
| 12 | adventureworks_query_2.json | Ejemplo de conteo de clientes recientes. | `nl2sql-indexer` | `samples/sql_database/queries/adventureworks_query_2.json` |
| 13 | adventureworks_query_3.json | Query multi-join para clientes de categoría Bikes. | `nl2sql-indexer` | `samples/sql_database/queries/adventureworks_query_3.json` |
| 14 | adventureworks_query_4.json | Query de productos descontinuados. | `nl2sql-indexer` | `samples/sql_database/queries/adventureworks_query_4.json` |
| 15 | adventureworks_query_5.json | Query de ventas/impuestos del último año. | `nl2sql-indexer` | `samples/sql_database/queries/adventureworks_query_5.json` |
| 16 | adventureworks-saleslt_address.json | Catálogo semántico de tabla de direcciones. | `nl2sql-indexer` | `samples/sql_database/tables/adventureworks-saleslt_address.json` |
| 17 | adventureworks-saleslt_customer.json | Catálogo semántico de clientes. | `nl2sql-indexer` | `samples/sql_database/tables/adventureworks-saleslt_customer.json` |
| 18 | adventureworks-saleslt_product.json | Catálogo semántico de productos. | `nl2sql-indexer` | `samples/sql_database/tables/adventureworks-saleslt_product.json` |
| 19 | adventureworks-saleslt_productcategory.json | Catálogo semántico de categorías de producto. | `nl2sql-indexer` | `samples/sql_database/tables/adventureworks-saleslt_productcategory.json` |
| 20 | adventureworks-saleslt_productdescription.json | Catálogo semántico de descripciones de producto. | `nl2sql-indexer` | `samples/sql_database/tables/adventureworks-saleslt_productdescription.json` |
| 21 | adventureworks-saleslt_productmodel.json | Catálogo semántico de modelos de producto. | `nl2sql-indexer` | `samples/sql_database/tables/adventureworks-saleslt_productmodel.json` |
| 22 | adventureworks-saleslt_salesorderdetail.json | Catálogo semántico de detalle de órdenes. | `nl2sql-indexer` | `samples/sql_database/tables/adventureworks-saleslt_salesorderdetail.json` |
| 23 | adventureworks-saleslt_salesorderheader.json | Catálogo semántico de cabeceras de órdenes. | `nl2sql-indexer` | `samples/sql_database/tables/adventureworks-saleslt_salesorderheader.json` |

### 4.3 Samples NL2SQL (Fabric)

| # | Directorio/archivo | Descripción (1 oración) | Componentes que demuestra | Ruta relativa |
|---|---|---|---|---|
| 24 | datasources.json | Define datasources de Fabric (`sql_endpoint` y `semantic_model`). | `nl2sql-indexer` | `samples/fabric/datasources.json` |
| 25 | wwi_sales_aggregate_data_query_1.json | Query DAX de top empleados por ventas. | `nl2sql-indexer`, `NL2SQLChunker` | `samples/fabric/queries/wwi_sales_aggregate_data_query_1.json` |
| 26 | wwi_sales_aggregate_data_query_2.json | Query DAX de top ciudades por profit. | `nl2sql-indexer` | `samples/fabric/queries/wwi_sales_aggregate_data_query_2.json` |
| 27 | wwi_sales_aggregate_data_query_3.json | Query DAX de ventas por ciudad/año. | `nl2sql-indexer` | `samples/fabric/queries/wwi_sales_aggregate_data_query_3.json` |
| 28 | aggregate_sale_by_date_city | Tabla agregada por ciudad y fecha. | `nl2sql-indexer` | `samples/fabric/tables/wwi_sales_aggregated_data-aggregate_sale_by_date_city.json` |
| 29 | aggregate_sale_by_date_employee | Tabla agregada por empleado y fecha. | `nl2sql-indexer` | `samples/fabric/tables/wwi_sales_aggregated_data-aggregate_sale_by_date_employee_.json` |
| 30 | dimension_city | Dimensión geográfica de ciudad. | `nl2sql-indexer` | `samples/fabric/tables/wwi_sales_star_schema-dimension_city.json` |
| 31 | dimension_customer | Dimensión de clientes. | `nl2sql-indexer` | `samples/fabric/tables/wwi_sales_star_schema-dimension_customer.json` |
| 32 | dimension_date | Dimensión calendario/fiscal. | `nl2sql-indexer` | `samples/fabric/tables/wwi_sales_star_schema-dimension_date.json` |
| 33 | dimension_employee | Dimensión de empleados de ventas. | `nl2sql-indexer` | `samples/fabric/tables/wwi_sales_star_schema-dimension_employee.json` |
| 34 | dimension_stock_item | Dimensión de inventario/producto. | `nl2sql-indexer` | `samples/fabric/tables/wwi_sales_star_schema-dimension_stock_item.json` |
| 35 | fact_sale | Tabla de hechos de ventas. | `nl2sql-indexer` | `samples/fabric/tables/wwi_sales_star_schema-fact_sale.json` |

---

## 5. Combinaciones de Componentes Recomendadas

### 5.1 Patrones frecuentes recomendados

1. **RAG documental estándar**
- `blob-storage-indexer` + (`DocAnalysisChunker` o `LangChainChunker`) + `blob-storage-indexer-purger`

2. **RAG multimodal (texto + figuras)**
- `blob-storage-indexer` + `MultimodalChunker` + `multimodality-images-purger`

3. **RAG empresarial SharePoint**
- `sharepoint-indexer` + `sharepoint-purger` + ACL/RBAC metadata

4. **NL2SQL productivo**
- `nl2sql-indexer` + `nl2sql-indexer-purger` + separación por índices (`queries/tables/measures`)

5. **Batch robusto nocturno**
- `blob-storage-indexer` (con retries/backoff ajustados) + purga posterior + observabilidad de run logs

### 5.2 Anti-patrones a evitar

1. Ejecutar indexación sin purga periódica.
- Provoca drift entre fuente e índice.

2. Tratar todos los tipos de archivo con un único chunker genérico.
- Reduce calidad semántica y recuperación.

3. Subir cargas masivas sin tuning de concurrencia ni límites de OpenAI.
- Incrementa errores 429 y tiempo total de proceso.

4. Activar multimodal sin limpiar imágenes huérfanas.
- Aumenta costo de almacenamiento y ruido operacional.

5. En SharePoint, no definir claramente listas/filtros en configuración de Cosmos.
- Eleva costo de crawling y riesgo de indexar contenido no deseado.
