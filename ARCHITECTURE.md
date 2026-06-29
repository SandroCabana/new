# Arquitectura del Sistema de Recomendación LTI: Desglose de Funcionalidades

El proyecto adopta una arquitectura modular de microservicios contenerizados, centrada en un modelo de identidad Hub-and-Spoke y un motor híbrido de inteligencia artificial. Esta separación por responsabilidades permite el escalamiento independiente de cada componente (rastreo asíncrono, procesamiento por lotes, búsqueda vectorial y presentación). A continuación, se presenta el desglose funcional de las ocho capas clave de la arquitectura.

---

## 1. Capa de Identidad e Integración (LTI 1.3 & Auth)

Esta capa es el punto de entrada principal para los usuarios y gestiona la relación segura y estandarizada entre el Sistema de Gestión del Aprendizaje (LMS), en este caso Moodle, y el ecosistema de recomendación. 

- **LTI 1.3 Advantage Launch:** Actúa como el puente inicial que proporciona autenticación segura y funcionalidad de "Deep Linking" desde el Entorno Personal de Aprendizaje (PLE) en Moodle hacia el panel de recomendaciones personalizado del estudiante.
- **Hub-and-Spoke Identity Model:** Aborda el reto de tener múltiples identificadores desconectados al unificar identidades locales (ej. cuentas de Moodle, de Canvas, etc.) bajo un modelo de un único usuario global persistente (`GlobalUser`). Este enfoque permite centralizar la historia y preferencias del estudiante con independencia de su plataforma de origen.
- **JWT Handshake & Auto-Pairing:** Se establece un mecanismo de autenticación sin fricción para emparejar la extensión de navegador del estudiante de manera automática. A través del intercambio de tokens seguros JWT generados desde la sesión LTI activa, se vincula el cliente del navegador con el usuario global sin exigir inicios de sesión manuales.
- **Gestión de Contextos:** El sistema identifica automáticamente el origen de la sesión, extrayendo metadatos clave como el curso de procedencia, el rol del usuario (estudiante vs. instructor) y el LMS originario, lo que permite contextualizar tanto el registro de datos como las recomendaciones emitidas.

---

## 2. Capa de Captura y Rastreo (Browser Extension)

Esta capa funciona como el "agente" de campo del proyecto, encargándose de observar y recolectar la experiencia de aprendizaje del usuario fuera del entorno controlado del LMS.

- **Multitask Content Tracking:** La extensión está diseñada para manejar sesiones complejas de navegación. Rastrea el progreso de forma independiente para múltiples pestañas abiertas simultáneamente de manera transparente, asegurando que el contexto y los metadatos de diferentes recursos no se mezclen.
- **Semantic Metadata Extraction:** En lugar de rastrear simplemente URLs, la extensión emplea técnicas para extraer automáticamente el título real del contenido, su descripción, palabras clave (keywords) y determina dinámicamente la duración teórica o práctica de la actividad.
- **Engagement Scoring:** Se implementan métricas para calcular un nivel de compromiso (engagement). El sistema procesa la profundidad de scroll, evalúa el porcentaje de tiempo activo en contraposición con el tiempo pasivo (sin interacción) e incorpora heurísticas para detectar el visionado de elementos multimedia como videos.
- **Privacy-First Domain Filtering:** Para preservar rigurosamente la privacidad del estudiante, la captura de datos no es global. Está circunscrita a una "lista blanca" configurable de dominios y repositorios educativos explícitamente permitidos para el rastreo.

---

## 3. Capa de Procesamiento Inteligente (Celery & ML Workers)

Funciona como el "cerebro asíncrono" del sistema, asegurando que las tareas computacionalmente intensivas operen en segundo plano sin ralentizar ni bloquear la experiencia del usuario.

- **Asynchronous Batch Processing:** Facilita la ingesta masiva y no bloqueante de datos. A medida que el usuario navega, los eventos son encolados (vía Redis) y posteriormente digeridos por trabajadores (workers) independientes dedicados a tareas específicas, como scraping o entrenamiento de machine learning.
- **Incremental Embedding Generation:** Uno de los puntos focales del procesamiento inteligente. Utiliza Sentence Transformers (en particular el modelo `paraphrase-multilingual-mpnet-base-v2`) para transcodificar dinámicamente textos, títulos y resúmenes de recursos web en vectores matemáticos densos de 768 dimensiones.
- **Auto-Update or Create:** Implementa una lógica de consolidación inteligente. Si un recurso educativo web cambia o la extensión captura metadatos de mayor calidad, el trabajador de Celery enriquece las entradas antiguas del recurso de forma incremental en lugar de sobrescribirlas destructivamente.
- **Nightly Model Retraining:** El entrenamiento de los modelos de recomendación se delega a tareas programadas (vía Celery Beat), las cuales reentrenan por las noches los parámetros de algoritmos colaborativos (SVD, NCF, FM) aprovechando los nuevos datos transaccionales del día.

---

## 4. Capa de Recomendación (Hybrid Ensemble Engine)

Es el núcleo decisional de la arquitectura. Esta capa se responsabiliza de sopesar, calcular y decidir qué objeto de aprendizaje tiene mayor probabilidad de ser útil y relevante para un estudiante dado.

- **Hybrid Ensemble Architecture:** Supera las limitaciones de enfoques individuales (como el problema del *Cold-Start* del filtro colaborativo o el encasillamiento del filtrado de contenido) orquestando la salida combinada de 5 modelos de manera simultánea: Factorización de Matrices (SVD), Neural Collaborative Filtering (NCF), Factorization Machines (FM), Recomendación Secuencial (Secuencial Rec) y Búsqueda Semántica de Contenido.
- **Vectorial Semantic Search:** Provee velocidad extrema al cotejar similitudes. Integrado a nivel de base de datos a través de `pgvector`, emplea indexación de tipo HNSW (Hierarchical Navigable Small World) para ejecutar búsquedas exhaustivas por similitud de coseno en milisegundos.
- **Dynamic Weighting:** El sistema no utiliza una ponderación rígida para la combinación (ensemble). Los pesos de los modelos cambian dinámicamente en función del perfil del estudiante; por ejemplo, si un alumno es nuevo (Cold-Start), se otorgan pesos muy superiores al motor semántico y secuencial antes que a los motores puramente colaborativos.
- **Explainable Recommendations:** No basta con sugerir; se provee el origen o la justificación computacional detrás de la recomendación (ej. "Recomendado por su alta similitud semántica con tu interés en Python"), aumentando así la confianza del estudiante en el sistema.

---

## 5. Capa de Persistencia y Datos (Database Layer)

El ecosistema de bases de datos que sostiene la verdad inmutable del estado del sistema, diseñado para equilibrar consultas relacionales, búsquedas vectoriales y baja latencia de caché.

- **Relational Storage (PostgreSQL):** Funciona como la piedra angular para las transacciones ACID, alojando de forma consistente los perfiles de usuario unificados (GlobalUser), el registro estructurado de interacciones LTI y xAPI, y el catálogo maestro de recursos educativos.
- **Vector Database (pgvector):** Extiende nativamente las capacidades de PostgreSQL para convertirlo en una base de datos vectorial de estado del arte. Aquí se almacenan los embeddings matemáticos de 768 dimensiones generados previamente y se ejecuta la búsqueda profunda por similitud vectorial.
- **State Cache (Redis):** Mantiene una capa de almacenamiento temporal en memoria. Su rol principal es alojar el broker y el backend de resultados para las colas asíncronas de Celery, pero también orquesta el almacenamiento en caché de recomendaciones recientes, logrando despachar sugerencias personalizadas en menos de 50 milisegundos.

---

## 6. Capa de Observabilidad y Admin

Un conjunto de herramientas y dashboards críticos para auditar, controlar e interpretar el comportamiento del sistema a gran escala. 

> **Justificación Técnica**: El uso integrado de `pgvector` acoplado con motores SBERT sitúa arquitectónicamente al presente proyecto en la frontera tecnológica del *Estado del Arte* en materia de "Recomendaciones Basadas en Contenido Semántico", logrando trascender significativamente a los enfoques tradicionales de la literatura que basan sus sugerencias exclusivamente en taxonomías estáticas, metadata manual o comparación literal de palabras clave.

- **Dashboard de Administración:** Aporta una interfaz segura e integral que permite al administrador inspeccionar los recursos indexados, supervisar las métricas descriptivas de los usuarios en tiempo real, visualizar telemetría y vigilar la salud técnica y analítica de los modelos ML operativos.
- **Unified Logging System:** Centraliza un registro de logs a través del entorno de contenedores Docker. Garantiza un nivel de auditoría detallado para rastrear en tiempo real errores en los workers de inteligencia artificial y rastrear inconsistencias de procesamiento y persistencia.

---

## 7. Capa de Adquisición y Enriquecimiento (Data Scraper)

Subsistema automatizado que garantiza que el acervo de la plataforma (el catálogo de recomendaciones) mantenga altos estándares de calidad, completitud y disponibilidad. 

- **Automated Content Scraping:** A través de tareas asíncronas programadas, spiders autónomos visitan en segundo plano las URLs aportadas de manera orgánica. Su fin es rastrear y extraer el texto completo, autores y contexto que la extensión de navegador no está capacitada o autorizada a capturar de inmediato.
- **Auto-Tagging Engine:** Un proceso posterior a la recolección textual que somete el texto íntegro extraído a técnicas de NLP ligeras para derivar e inferir de forma automática etiquetas taxonómicas (tags), contribuyendo a una clasificación temática estructurada del catálogo.
- **Resource Validation:** Rutinas programadas de "Health Check" que recorren el índice vectorial del sistema verificando de manera continua que las URLs recomendadas no apunten a enlaces rotos (error 404), garantizando que el usuario final solo acceda a recursos educativos verdaderamente disponibles.

---

## 8. Capa de Datos de Entrenamiento (Interaction Datasets)

Capa fundacional indispensable para pre-entrenar y robustecer los algoritmos colaborativos, evitando desplegar un sistema "vacío" sin capacidad predictiva.

- **Kaggle E-Learning Dataset Integration:** Una canalización (pipeline) para normalizar, procesar e ingerir *datasets* de interacciones masivas y probadas del ámbito educativo (como los hallazgos en Kaggle). Esto proporciona un pre-entrenamiento base crucial para los motores de Factorización Matricial y Redes Neuronales.
- **Cross-Domain Knowledge Transfer:** Adopta una estrategia técnica orientada a mitigar drásticamente el problema de arranque en frío (Cold-Start) inherente al despliegue de nuevos módulos en Moodle. Se transfieren relaciones latentes de interés a partir de comportamientos preexistentes en dominios externos de aprendizaje.
- **Data Augmentation:** En aras de proveer suficiente volumen y diversidad a la arquitectura de Red Neuronal Colaborativa (Neural CF), se emplean técnicas de generación y síntesis de registros que actúan sobre perfiles estudiantiles base, multiplicando las trayectorias posibles para robustecer la fase de ajuste fino del modelo matemático.
