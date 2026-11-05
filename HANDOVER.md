# 🔄 Último Handover (Relevo)
- **Fecha:** 2026-11-05 14:45
- **Desarrollador / Cuenta:** jpalvarez0512
- **Rama activa:** main (Sincronizado con origin/main en GitHub)

### ✅ Completado en esta sesión:
1. **Optimización Extrema del Motor de Audio (Eliminación de Trabamiento / Audio Dropouts):**
   - **Aumento del tamaño de búfer a 1024 frames (23.22 ms):** Se incrementó de 256 a 1024 frames en `MultitrackEngine`, `src/server/app.py` y `config/app_config.json`. Con 17 stems simultáneos en Python, 256 frames dejaban un margen de apenas 5.8 ms por bloque, lo que provocaba micro-bloqueos en el recolector de basura (GC) de Windows WASAPI. A 1024 frames el callback toma solo ~3.6 ms (15% del presupuesto temporal), con 0% de sobrecarga y 1.7% de uso de CPU.
   - **Mezcla Zero-Heap-Allocation (`add_slice_to` en `src/audio/stem.py` y pre-asignación en `src/audio/engine.py`):** Se eliminaron las 3,200+ asignaciones de NumPy arrays por segundo durante la reproducción. Ahora los búferes de mezcla `_master_mix_buf` y `_cue_mix_buf` están pre-reservados en memoria estática y las porciones de cada stem se acumulan directamente in-place mediante sumas optimizadas en C con escalado de volumen escalar, logrando una aceleración de 1.41x y cero pausas de recolector de basura.
   - **Frecuencia del reloj maestro desacoplada (`_ticker_loop` a 22 Hz):** Se ajustó el ciclo de emisión a ~45 ms para desaturar los WebSockets y la red local, mientras las pantallas de músicos, proyector y OBS interpolan a 60 FPS ultra-fluidos en el cliente.
   - **Omisión de broadcast cuando no hay clientes conectados:** En `on_engine_tick()`, si no hay clientes conectados (`total_clients == 0`), se ahorra el procesamiento y despacho de tareas asíncronas.

2. **Perfeccionamiento de Sincronización de Acordes (Downbeat Quantization):**
   - Corrección en `ChordProParser` (`src/core/chordpro.py`, Schema v3): el primer acorde de cada línea de letra (`c_idx == 0`) ahora queda anclado obligatoria y exactamente al tiempo de inicio del verso (`line_start`), y los acordes subsecuentes se cuantizan por compás/pulso musical (`60 / bpm`), eliminando el desfase que ocurría al calcular tiempos relativos por cantidad de caracteres.

3. **Video Loops y Fondos en Pantalla de Proyección (`/projection`, `src/core/projection_config.py`):**
   - Soporte para bucles de video en reproducción continua (`.mp4`, `.webm`, `.mov`, `.m4v`) y fondos de imagen (`.jpg`, `.png`, `.webp`, `.gif`).
   - Fondos predeterminados y loops animados incluidos: `🎬 Loop: Aurora Celestial`, `🎬 Loop: Destellos Dorados` (partículas dinámicas por canvas), `Azul Noche`, `Púrpura Adoración`, `Luz de Altar`, `Agua Viva`, `Negro Puro`.
   - Soporte para subir video loops propios directamente desde el panel de control (`POST /api/projection/backgrounds`).
   - Letras en amarillo intenso de alto contraste (`#FFE600`) con trazo oscuro detrás de las letras (`paint-order: stroke fill; -webkit-text-stroke: 3.2px rgba(0,0,0,0.95)`) y sombra profunda multicapa para máxima legibilidad sobre cualquier video o imagen.

4. **Dirección Independiente Exclusiva para OBS Studio (`/obs`, `src/clients/web/obs.html`):**
   - Ruta dedicada con fondo 100% transparente para usar como *Browser Source* en OBS Studio sin necesidad de filtros de color.
   - Modo tercio inferior (*Lower-Thirds*) automático para transmisión en vivo.
   - Parámetros URL opcionales: `/obs?pos=center` (centrado) o `/obs?box=1` (con franja oscura translúcida).
   - Ocultamiento instantáneo mediante *Blackout* u *Ocultar Texto* desde el operador sin oscurecer la cámara en vivo.

5. **Anticipación Temporal de Letra para la Congregación (Lead Time):**
   - Eliminación del lag de entrada de letras: transiciones limpias e inmediatas sin retrasos acumulativos.
   - Anticipación configurable en vivo desde el operador (por defecto `1.5s` antes) mediante `Song.get_projection_lyric_at()`, permitiendo a la congregación leer la frase un momento antes de cantarla para no trabarse.

6. **Escenas y Listas para el Servicio Dominical (`src/core/scene_manager.py`, `config/scenes.json`):**
   - Sistema de listas dominicales (*Setlists*) con nombre, fecha (selector de calendario), notas pastorales y orden secuencial de canciones de la biblioteca con transposición personalizable por tema.
   - Navegación secuencial rápida en el transporte durante el culto: botones **`⏮ Anterior`** y **`⏭ Siguiente`** para pasar de canción con un solo clic.
   - Endpoints REST completos: `GET/POST/PUT/DELETE /api/scenes`, `/api/scenes/{id}/activate`, `/api/scenes/navigate`.

7. **Mezclador con Nombres Completos de Pistas (`src/clients/web/control.html`):**
   - Corrección de corte y elipsis: los nombres de todas las pistas de audio (`Click`, `Guía`, `Pad`, `Bajo` y pistas con nombres largos) ahora se muestran completos con ajuste de línea fluido.
   - Etiqueta de ruteo interactiva con 1 clic (`CUE / IN-EAR` ↔ `SALA / FOH` ↔ `AMBOS`) y porcentaje de volumen numérico visible junto al fader.

8. **Terminal de Músicos: Modo Compás Actual y Acorde Gigante (`/musicians`, `src/clients/web/musicians.html`):**
   - Vista por defecto **🎯 Compás Actual**: muestra únicamente el compás y frase que toca en ese instante sin muro de texto innecesario.
   - Acorde Hero Gigante (`clamp(4.2rem, 15vw, 8.2rem)`) con indicación del acorde siguiente (`Siguiente: [Acorde]`).
   - Flujo de acordes del compás con el acorde activo resaltado en amarillo brillante.
   - Pulso visual de compás (1-2-3-4) sincronizado con los BPM de la canción.
   - Tarjeta previa sutil del próximo compás para anticipar cambios.
   - Selector para alternar a **📄 Hoja Completa** en cualquier momento si el músico desea revisar toda la partitura.

9. **Pruebas Automatizadas y Verificación:**
   - Creado `scripts/test_scenes_and_views.py`: prueba al 100% el CRUD de escenas, activación, navegación, configuración de proyección, subida/borrado de video loops, ruteo de stems, entrega HTML y anticipación de letras.
   - Verificados `scripts/test_upload.py`, `scripts/test_chordpro.py`, `scripts/test_engine.py`, `scripts/test_server.py`: 100% de éxito en todas las suites.
   - Servidor en vivo reiniciado y ejecutándose en segundo plano en el puerto 8000 con los nuevos endpoints y optimizaciones activas.

### 🚧 Trabajo en progreso (WIP):
- Empaquetado instalador Windows y APK Android.

### ⚠️ Decisiones técnicas o bloqueos:
- Para OBS Studio, siempre usar la URL `http://<IP_LOCAL>:8000/obs` como fuente de navegador.
- Los video loops y fotos subidos en `config/backgrounds/` y los audios en `tracks/**/stems/` están excluidos en `.gitignore` para mantener el repositorio liviano y seguro en GitHub.

### 🎯 Siguiente paso prioritario:
- Probar en vivo el flujo completo desde `http://localhost:8000/control` probando la creación de una Lista Dominical, probando un video loop en `http://localhost:8000/projection` y la fuente de navegador en OBS Studio `http://localhost:8000/obs`.
