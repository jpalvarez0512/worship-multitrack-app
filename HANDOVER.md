# 🔄 Último Handover (Relevo)
- **Fecha:** 2026-11-04 17:14
- **Desarrollador / Cuenta:** jpalvarez0512
- **Rama activa:** main (Sincronizado con origin/main en GitHub)

### ✅ Completado en esta sesión:
- **Parser de Formato ChordPro con Marcas de Tiempo (`src/core/chordpro.py`):**
  - Soporte para directivas estándar: `{title}`, `{artist}`, `{key}`, `{bpm}`, `{time}`, `{section}` / `{c}`.
  - Soporte de marcas de tiempo al inicio de línea: `[mm:ss.xx]`, `[ss.xx]`, `[mm:ss]`.
  - Separación automática en dos salidas:
    - *Pantalla de Músicos:* Acordes `[G]`, `[Em7]`, `[D/F#]` con cálculo de tiempo métrico proporcional y transposición armónica dinámica.
    - *Pantalla de Proyección:* Letra 100% limpia sin etiquetas técnicas ni corchetes.
  - Serialización y deserialización bidireccional con `song.json`.
- **Cargador de Biblioteca de Canciones (`src/core/song_loader.py`):**
  - Escaneo automático de la carpeta `tracks/`.
  - Detección inteligente de archivos `chart.pro`, `chart.txt` y `song.json` con regeneración automática cuando el archivo de texto cambia.
  - Carga de pistas de audio reales desde `tracks/<cancion>/stems/` o generación automática de audio sintético si no hay archivos cargados aún.
- **Gestión de Canciones en la API REST y WebSockets (`src/server/app.py`):**
  - `GET /api/songs`: Lista de canciones en disco con conteo de stems y estado.
  - `POST /api/songs/{id}/load`: Carga y cambio de canción en vivo, notificando a todos los móviles y proyectores conectados vía WebSocket (`song_changed`).
  - `POST /api/songs/parse-preview`: Vista previa en tiempo real del parsing sin guardar.
  - `POST /api/songs/import`: Creación de nuevas canciones a partir de texto ChordPro pegado.
- **Consola Web con Editor e Importador Integrado (`src/clients/web/control.html`):**
  - Selector de canciones en vivo en la barra superior.
  - Modal para pegar texto ChordPro, botón de "Vista Previa" con división visual lado a lado (Músicos vs Proyección) y botón "Guardar y Cargar a la App".
- **Canciones de Demostración Iniciales:**
  - `tracks/cuan-grande-es-dios/`: Canción completa con 6 secciones y estructura ChordPro.
  - `tracks/gracia-sublime-es/`: Canción importada y verificada.
- **Pruebas Automatizadas:**
  - `scripts/test_chordpro.py`: 100% de éxito validando parsing, extracción limpia, escaneo de disco, API y cambio de canción.

### 🚧 Trabajo en progreso (WIP):
- Carga de archivos de audio reales (WAV/MP3) en las carpetas `tracks/<cancion>/stems/`.
- Empaquetado APK para Android o ejecutable portable para Windows.

### ⚠️ Decisiones técnicas o bloqueos:
- Todo funciona en red local sin conexión a internet.
- Cada canción en `tracks/` mantiene su independencia con su propio `chart.pro`, `song.json` y carpeta `stems/`.

### 🎯 Siguiente paso prioritario:
- Iniciar el servidor local (`python main.py`), conectar dispositivos de prueba o empaquetar la aplicación cliente para Android.
