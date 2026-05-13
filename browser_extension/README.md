# LTI Learning Tracker - Chrome Extension

Extensión de Chrome para trackear sesiones de aprendizaje y sincronizar con el sistema de recomendaciones LTI Moodle.

## Instalación en Modo Desarrollador

1. Abre Chrome y navega a `chrome://extensions/`
2. Activa **"Modo desarrollador"** (esquina superior derecha)
3. Click en **"Cargar descomprimida"**
4. Selecciona esta carpeta (`browser_extension/`)
5. La extensión aparecerá en la barra de herramientas

## Configuración y Vinculación (Auto-Pairing)

La extensión ahora cuenta con **vinculación automática** para simplificar la experiencia del usuario:

1. **Vía Moodle (Recomendado)**: 
   - Simplemente abre el **LTI Recommender** dentro de tu curso de Moodle.
   - La extensión detectará automáticamente tu sesión e identidad global.
   - Aparecerá el estado **🔗 Conectado** en el popup de forma automática.
   - No necesitas copiar y pegar tokens.

2. **Configuración Manual (Opcional/Dev)**:
   - Ve a la pestaña **Config**.
   - **URL del API**: `http://localhost:8080` (o la URL de tu servidor).
   - **Contexto**: Puedes elegir tu curso actual desde el selector desplegable (se cargan automáticamente si estás vinculado) o ingresar uno manual.

## Uso

### 🚀 Iniciar Sesión de Aprendizaje
1. Abre el popup de la extensión.
2. Haz clic en **"Iniciar Sesión"**.
3. Navega por recursos educativos (YouTube, Wikipedia, artículos, etc.). La extensión capturará el tiempo de permanencia, profundidad de scroll y metadatos del recurso.
4. Haz clic en **"Pausar Sesión"** al terminar.

### 📤 Sincronización Asíncrona
1. Los datos se guardan de forma segura en el almacenamiento local de tu navegador.
2. Haz clic en **"Enviar al Servidor"**.
3. El sistema procesará los datos en segundo plano (vía Celery) para actualizar tus recomendaciones personalizadas.
4. Revisa tu **Historial** en la extensión para ver tus últimas actividades registradas.


### Ver Historial
1. Ve a la pestaña **Historial**
2. Verás tus estadísticas e interacciones registradas

## Estructura de Archivos

```
browser_extension/
├── manifest.json           # Configuración de la extensión (Manifest V3)
├── popup/
│   ├── popup.html          # UI principal
│   ├── popup.css           # Estilos
│   └── popup.js            # Lógica del popup
├── background/
│   └── service-worker.js   # Tracking en background
├── content/
│   └── tracker.js          # Extracción de metadata de páginas
├── icons/                  # Íconos de la extensión
│   ├── icon16.png
│   ├── icon48.png
│   └── icon128.png
└── README.md               # Este archivo
```

## API Endpoints Utilizados

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/interactions/user-history/` | GET | Historial de interacciones |
| `/interactions/user-stats/` | GET | Estadísticas del usuario |
| `/interactions/preview/` | POST | Vista previa antes de enviar |
| `/interactions/tracked-data-batch/` | POST | Enviar datos al servidor |

## Notas de Desarrollo

- **Manifest V3**: Usa service workers en lugar de background pages
- **Permisos**: `storage`, `tabs`, `activeTab`, `alarms`
- **Almacenamiento**: Datos guardados localmente en `chrome.storage.local`
- **Tiempo mínimo**: Solo registra páginas con > 5 segundos de visita
