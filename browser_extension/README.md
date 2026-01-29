# LTI Learning Tracker - Chrome Extension

Extensión de Chrome para trackear sesiones de aprendizaje y sincronizar con el sistema de recomendaciones LTI Moodle.

## Instalación en Modo Desarrollador

1. Abre Chrome y navega a `chrome://extensions/`
2. Activa **"Modo desarrollador"** (esquina superior derecha)
3. Click en **"Cargar descomprimida"**
4. Selecciona esta carpeta (`browser_extension/`)
5. La extensión aparecerá en la barra de herramientas

## Configuración

1. Click en el ícono de la extensión
2. Ve a la pestaña **Config**
3. Ingresa:
   - **URL del API**: `http://localhost:8000` (o tu servidor de producción)
   - **Contexto**: ID del curso Moodle
4. Click **"Conectar con Moodle"** e ingresa tu token de autenticación
5. Click **"Guardar Configuración"**

## Uso

### Iniciar Sesión de Tracking
1. Click en el ícono de la extensión
2. Click **"Iniciar Sesión"**
3. Navega normalmente - todas las páginas serán registradas
4. Click **"Pausar Sesión"** cuando termines

### Revisar y Enviar Datos
1. Los datos se guardan localmente primero
2. En la sección **"Datos Pendientes"**, click **"Vista Previa"**
3. Revisa qué datos serán enviados
4. Click **"Confirmar y Enviar"** para sincronizar con el servidor

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
