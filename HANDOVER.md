# 🔄 Último Handover (Relevo)
- **Fecha:** 2026-11-05 11:23
- **Desarrollador / Cuenta:** jpalvarez0512
- **Rama activa:** main (Sincronizado con origin/main en GitHub)

### ✅ Completado en esta sesión:
- **Subida y Gestión Completa de Canciones desde la Web (`src/server/app.py`, `src/core/song_loader.py`):**
  - `POST /api/songs/upload`: Crea una canción directamente desde el navegador subiendo archivo ChordPro (`.pro`, `.txt`, `.cho`) o pegando texto, junto con múltiples pistas de audio (`.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`, `.aiff`).
  - `POST /api/songs/{id}/stems` y `DELETE /api/songs/{id}/stems/{filename}`: Permite agregar o eliminar pistas individuales de una canción existente en cualquier momento.
  - `GET /api/songs/{id}/chart` y `PUT /api/songs/{id}/chart`: Editor en vivo de la letra y acordes ChordPro conservando intactos los stems de audio.
  - `DELETE /api/songs/{id}`: Eliminación completa de canciones desde la biblioteca web.
  - Endpoints de subida y decodificación ejecutados en pool de hilos (no bloquean el loop asíncrono ni congelan los WebSockets de músicos/proyección durante subidas pesadas).
  - Normalización Unicode segura (`slugify`) para nombres de carpetas con tildes/eñes y soporte automático para archivos `.txt` codificados en UTF-8 o ANSI/Windows-1252 (Bloc de notas).
- **Nueva Biblioteca e Importador en la Consola Web (`src/clients/web/control.html`):**
  - Botón **⬆ Nueva Canción** con asistente en 3 pasos: metadatos, zona *drag & drop* para archivo ChordPro (o texto pegado con vista previa doble) y zona *drag & drop* múltiple para stems con detección anticipada de ruteo (`CUE / IN-EAR` vs `SALA / FOH`) y barra de progreso en tiempo real.
  - Panel **📚 Biblioteca de Canciones** con estado visual (`LETRA ✓`, `X PISTAS`) y acciones rápidas (`▶ Cargar`, `🎵 + Pistas`, `📝 Letra`, `🗑`).
  - Mejoras en `src/audio/stem.py`: soporte para WAV PCM 32-bit entero y palabras clave en español con tilde (`guía`, `metrónomo`, `clic`).
- **Pruebas Automatizadas:**
  - `scripts/test_upload.py`, `scripts/test_chordpro.py`, `scripts/test_server.py` y `scripts/test_engine.py`: 100% de éxito.

### 🚧 Trabajo en progreso (WIP):
- Prueba en vivo desde el navegador subiendo pistas reales del usuario.
- Empaquetado APK para Android o ejecutable portable para Windows.

### ⚠️ Decisiones técnicas o bloqueos:
- **Nota importante al actualizar código del servidor:** Si `main.py` ya estaba corriendo en una terminal abierta antes de actualizar el código, es necesario detenerlo (`Ctrl+C`) y volverlo a iniciar con `.\.venv\Scripts\python.exe main.py` para que cargue los nuevos endpoints en memoria (y usar siempre el Python de `.venv`).
- Los archivos de audio subidos en `tracks/**/` están protegidos en `.gitignore` para no saturar GitHub con archivos pesados, conservando versionados los `chart.pro` y `song.json`.

### 🎯 Siguiente paso prioritario:
- Abrir `http://localhost:8000/control`, probar el selector de canciones y subir una canción real con sus stems usando el botón **⬆ Nueva Canción**, o avanzar con el empaquetado Android (APK).
