# Guía General de la Solución: GPT-RAG Data Ingestion

## Tabla de contenidos
- [1. ¿Qué es GPT-RAG Data Ingestion?](#1-qué-es-gpt-rag-data-ingestion)
- [2. ¿Qué problema resuelve?](#2-qué-problema-resuelve)
- [3. Conceptos clave](#3-conceptos-clave)
- [4. Componentes principales](#4-componentes-principales)
- [5. ¿Cómo funciona el flujo completo?](#5-cómo-funciona-el-flujo-completo)
- [6. Servicios de Azure utilizados](#6-servicios-de-azure-utilizados)
- [7. Modos de despliegue](#7-modos-de-despliegue)
- [8. Ejemplo práctico](#8-ejemplo-práctico)
- [9. Resumen ejecutivo](#9-resumen-ejecutivo)

## 1. ¿Qué es GPT-RAG Data Ingestion?

Es la capa de “preparación de contenido” del ecosistema GPT-RAG: toma documentos de negocio, los limpia, los parte en fragmentos útiles, crea vectores semánticos y los deja listos para búsqueda inteligente.

Analogía simple: es como una fábrica de biblioteca digital, donde entran archivos sin ordenar y salen “fichas inteligentes” listas para que un asistente de IA encuentre respuestas rápidas y confiables.

Propuesta de valor en una frase: convierte contenido empresarial heterogéneo en conocimiento indexado y reutilizable para experiencias RAG y agentes de IA.

Nota de alcance: este repositorio implementa el servicio de ingestión; la infraestructura completa de la solución GPT-RAG está en el repositorio principal de GPT-RAG.

## 2. ¿Qué problema resuelve?

| Desafío común | Cómo lo resuelve el proyecto |
|---|---|
| Documentos en muchos formatos (PDF, Office, imágenes, VTT, JSON) | Usa estrategias de chunking por tipo de archivo para procesar cada formato de forma adecuada. |
| Contenido no estructurado difícil de consultar | Convierte documentos en fragmentos pequeños con metadatos útiles para búsqueda. |
| Respuestas pobres por falta de contexto semántico | Genera embeddings de texto (y multimodal cuando aplica) para búsquedas vectoriales. |
| Fuentes distribuidas (Blob, SharePoint, NL2SQL) | Ejecuta indexadores especializados por origen y unifica el resultado en índices de Azure AI Search. |
| Datos eliminados que quedan “huérfanos” | Incluye purgas programadas para limpiar entradas obsoletas en índice y blobs auxiliares. |
| Operación manual y difícil de escalar | Orquesta ejecución por cron y jobs recurrentes, con observabilidad y logs por corrida. |
| Variaciones entre entornos | Centraliza configuración en Azure App Configuration (con labels) para consistencia. |

## 3. Conceptos clave

1. Chunking
Dividir un documento grande en bloques pequeños y útiles para IA.

Ejemplo mínimo de payload de entrada:
```yaml
values:
  - recordId: "1"
    data:
      documentUrl: "https://.../manual.pdf"
      documentContentType: "application/pdf"
```

2. Embeddings
Representación numérica del significado de texto para encontrar similitud, no solo palabras exactas.

Ejemplo mínimo:
```yaml
values:
  - recordId: "1"
    data:
      text: "Política de devoluciones para clientes enterprise"
```

3. Indexación
Publicar chunks y metadatos en Azure AI Search para consultas rápidas y filtrables.

4. Indexadores por fuente
Jobs distintos para Blob, SharePoint y NL2SQL; cada uno aplica reglas de detección de cambios, indexación y limpieza.

5. Configuración centralizada
El servicio obtiene claves y cron desde App Configuration (label del proyecto y label base), evitando “configuración dispersa”.

Diagrama ASCII de concepto central:
```text
Documento bruto -> Chunking -> Embeddings -> Índice AI Search -> Consumo por RAG/Agente
      (PDF, XLSX,            (vector)          (texto + vector)
       VTT, JSON...)
```

Diagrama ASCII de ejecución programada:
```text
App Configuration (cron) -> Scheduler -> Job (index/purge) -> Logs + Estado
```

## 4. Componentes principales

| Componente | Propósito | Tecnologías principales | Puerto |
|---|---|---|---|
| API de Ingestión | Exponer endpoints para chunking y embeddings bajo autenticación por API key | FastAPI, Uvicorn, jsonschema | 8080 (Container Apps); 80 en ejecución local directa |
| Motor de Chunking | Elegir estrategia de partición según formato de archivo | Python, ChunkerFactory, Document Intelligence, LangChain splitters | N/A |
| Jobs de Indexación/Purga | Sincronizar contenido desde orígenes y limpiar obsoletos | APScheduler, Azure Storage SDK, Azure AI Search SDK | N/A |
| Capa de Integración Azure | Conectar con App Config, Key Vault, OpenAI, Search, Blob, Cosmos y Graph | SDKs de Azure, identidad administrada, Azure CLI credential fallback | N/A |
| Observabilidad | Trazas, métricas y logs para operación y soporte | OpenTelemetry, Azure Monitor / App Insights | N/A |

Interconexión general:
```text
                +----------------------------+
                | Azure App Configuration    |
                +-------------+--------------+
                              |
                         (config/cron)
                              v
+-----------+         +-------+--------+         +------------------+
| Fuentes   +-------->+ Ingestion API  +-------->+ Azure AI Search  |
| Blob/SP   |         | + Scheduler    |         | (índices RAG)    |
| NL2SQL    |         +-------+--------+         +------------------+
+-----------+                 |
                              v
                     +--------------------+
                     | Azure OpenAI       |
                     | (embeddings)       |
                     +--------------------+
```

## 5. ¿Cómo funciona el flujo completo?

1. Un usuario/equipo carga o actualiza contenido en Blob Storage, SharePoint o contenedores NL2SQL.
2. El servicio lee configuración y cron desde App Configuration al arrancar.
3. El scheduler dispara jobs de indexación y purga según las ventanas definidas.
4. Cada job detecta cambios (nuevo, modificado o eliminado) para procesar solo lo necesario.
5. El motor de chunking selecciona la estrategia correcta por tipo de archivo.
6. Se generan embeddings para enriquecer recuperación semántica.
7. Los documentos/chunks se publican en Azure AI Search con metadatos de trazabilidad.
8. Jobs de limpieza eliminan registros o imágenes que ya no tienen referencia válida.
9. La aplicación de chat/agente consume el índice actualizado y responde con mayor precisión.

Flujo de datos (ASCII):
```text
[Blob/SharePoint/NL2SQL]
          |
          v
[Detección de cambios]
          |
          v
[Chunking por formato] --> [Embeddings]
          |                     |
          +----------+----------+
                     v
             [Azure AI Search]
                     |
                     v
              [App RAG / Agente]
```

## 6. Servicios de Azure utilizados

| Servicio | Propósito | SKU/Nivel recomendado |
|---|---|---|
| Azure Container Apps | Ejecutar la API y jobs con escalado administrado | Consumption para PoC; Dedicated Workload Profile para producción |
| Azure AI Search | Almacenar índice textual/vectorial para recuperación RAG | Basic para pruebas; Standard S1/S2 para producción |
| Azure OpenAI Service | Generar embeddings (y habilitar escenarios multimodales) | Según modelo y throughput; iniciar con cuota moderada por entorno |
| Azure App Configuration | Centralizar parámetros, claves de runtime y cron | Standard |
| Azure Key Vault | Guardar secretos y credenciales sensibles | Standard |
| Azure Storage Account (Blob) | Fuente documental y almacenamiento de logs/jobs | Standard GPv2, Hot/LRS al inicio |
| Azure Cosmos DB | Configuración dinámica de fuentes SharePoint/NL2SQL | Serverless para inicio; provisionado para carga estable |
| Application Insights + Azure Monitor | Observabilidad, telemetría y troubleshooting | Basado en volumen de telemetría |

## 7. Modos de despliegue

| Aspecto | Modo básico (PoC) | Modo enterprise/productivo |
|---|---|---|
| Objetivo | Validar rápido el caso de negocio | Operación confiable, segura y escalable |
| Red | Endpoints públicos controlados | Red privada, segmentación y egress controlado |
| Escalabilidad | Autoscaling por defecto | Autoscaling con límites, perfiles y capacidad reservada |
| Seguridad | API key + identidad administrada | Zero Trust: identidad administrada, secretos en KV, controles de acceso granulares |
| Operación | Monitoreo básico | Observabilidad completa, alertas y runbooks |
| Continuidad | Baja criticidad | Alta disponibilidad, política de backup/DR y gobierno |

Topología enterprise (ASCII):
```text
Usuarios/App RAG
      |
      v
[Front/API Layer]
      |
   Private Link / VNet Integration
      |
      +--> [Container Apps: Ingestion]
      +--> [Azure AI Search]
      +--> [Azure OpenAI]
      +--> [Storage + Cosmos]
      +--> [App Config + Key Vault]
      |
   [Azure Monitor / App Insights]
```

## 8. Ejemplo práctico

Caso: ingestión nocturna de políticas internas (PDF), manuales (DOCX) y catálogos (XLSX), más limpieza de documentos eliminados.

Pipeline YAML end-to-end (ilustrativo):
```yaml
pipeline:
  name: ingestion-nightly
  schedule: "0 2 * * *"
  source:
    - type: blob
      container: documents
    - type: sharepoint
      site: operaciones
  steps:
    - name: detect_changes
      action: compare_last_modified
    - name: chunk_documents
      action: call_endpoint
      endpoint: /document-chunking
    - name: generate_embeddings
      action: call_endpoint
      endpoint: /text-embedding
    - name: index_to_search
      action: upsert_documents
      target_index: ragindex
    - name: purge_deleted
      action: remove_orphans
    - name: emit_telemetry
      action: write_run_summary
```

Qué hace cada step en lenguaje natural:
- detect_changes: detecta solo archivos nuevos o modificados para reducir costo y tiempo.
- chunk_documents: parte documentos en fragmentos manejables para mejorar recuperación.
- generate_embeddings: traduce texto a vectores semánticos para búsqueda por significado.
- index_to_search: publica contenido enriquecido en el índice de Azure AI Search.
- purge_deleted: elimina registros o imágenes huérfanas para mantener consistencia.
- emit_telemetry: registra métricas, estado y diagnóstico de la corrida.

## 9. Resumen ejecutivo

| Aspecto | Detalle |
|---|---|
| Tipo de solución | Servicio de ingestión para arquitectura RAG empresarial |
| Arquitectura | Microservicio API + jobs programados + conectores de datos + búsqueda vectorial |
| Nube | Microsoft Azure |
| Servicios clave | Container Apps, AI Search, Azure OpenAI, App Configuration, Key Vault, Storage, Cosmos DB, Monitor/App Insights |
| Formatos soportados | PDF, imágenes, Office, VTT, JSON y contenido estructurado NL2SQL |
| Seguridad | API key, identidad administrada, secretos en Key Vault, configuración centralizada |
| Despliegue | Recomendado vía azd deploy sobre infraestructura GPT-RAG preexistente |
| Resultado para negocio | Menor tiempo para habilitar copilotos/QA corporativo con contenido confiable y actualizado |
