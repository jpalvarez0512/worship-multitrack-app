# 🔄 Último Handover (Relevo)
- **Fecha:** 2026-11-06 16:15
- **Desarrollador / Cuenta:** jpalvarez0512
- **Rama activa:** main (Sincronizado con origin/main en GitHub)

### ✅ Completado en esta sesión:
1. **Rediseño Estético Pro Hardware / Consola DAW (Anti-IA):**
   - **Eliminación del look "plástico / IA":** Se reemplazaron las esquinas hiper-redondeadas, degradados genéricos de Tailwind y botones planos por una estética profesional de hardware analógico/digital de rack (estilo Neve / Ableton Live / SSL / Teenage Engineering).
   - **Paleta de Hardware de Estudio:** Negro carbón mate (`#07090e`), grafito de chasis mecanizado (`#0e121b`), acentos en cian técnico (`#38bdf8`), verde consola (`#10b981`), ámbar cálido (`#f59e0b`) y carmesí (`#ef4444`).
   - **Master VFD / OLED Display Bezel:** Pantalla digital empotrada con bisel interior, reloj de transporte en fuente monospace/digital con resplandor de fósforo verde OLED (`00:00 / 04:12`), insignia `LIVE REC`, título de canción, tempo/tono (`BPM · Key`) y badge indicador de estado de guías de voz (`🎙️ GUÍAS: ON / OFF`).
   - **Botones de Transporte Físicos:** Botones estilo switch de estudio táctil con bisel 3D, relieves mecánicos y LEDs superiores de activación (Play en verde esmeralda, Pause en ámbar, Stop en rojo consola).
   - **Faders de Consola con Escala dB Serigrafiada:** Canales individuales para cada stem con escala grabada en decibelios (`+6, 0, -6, -12, -24, -∞`), faders estriados de aluminio pulido y switches mecánicos push-button para **Mute** (retroiluminación LED roja de estudio) y **Solo** (retroiluminación LED amarilla de estudio).
   - **Badges de Ruteo Patch-Bay:** Indicadores con relieve para `CUE / IN-EAR` (índigo profundo), `SALA / FOH` (verde esmeralda) y `AMBOS` (bronce dorado).

2. **Guías de Audio Dinámicas en In-Ears (Dynamic Cues On-The-Fly):**
   - **Banco de Voces en Español 100% Offline:** Generados 18 clips WAV normalizados a -1 dBFS en `assets/cues/` (`intro`, `verso`, `verso_1`, `verso_2`, `pre_coro`, `coro`, `puente`, `instrumental`, `solo`, `final`, `repite`, `atentos`, `corte`, `uno`, `dos`, `tres`, `cuatro`) mediante el script `scripts/generate_cues.py` utilizando el sintetizador nativo de Windows (Helena Desktop `es-ES`) sin requerir internet ni paquetes pesados.
   - **Módulo `CueManager` (`src/audio/cue_manager.py`):** Carga los clips en memoria RAM como arreglos NumPy `float32`, realiza matching inteligente de secciones musicales ("Coro 1" -> `coro`, "Verse 2" -> `verso_2`, etc.) y compone avisos combinados para bucles espontáneos ("Repite" + 80ms silencio + "[Sección]").
   - **Inyección en Tiempo Real en `MultitrackEngine` (`src/audio/engine.py`):**
     - Disparo automático de voz 1 compás antes de saltos cuantizados.
     - Aviso automático "Repite... [Sección]" 1 compás antes del límite de un bucle activo de ministración.
     - **Aislamiento Acústico Perfecto (0 Fuga):** En modo `SPLIT_STEREO`, el audio de las guías se inyecta exclusivamente en el canal izquierdo (L / In-Ears). El canal derecho (R / Sala - FOH) permanece en 0.000 absoluto, impidiendo que la congregación escuche las indicaciones internas.
     - Soporte para reproducción tanto durante el playback como con el transporte en pausa (soundcheck o avisos del director musical a los in-ears).
   - **Endpoints REST (`src/server/app.py`):**
     - `GET /api/transport/dynamic-cues`: Retorna el estado y los 18 avisos disponibles.
     - `POST /api/transport/dynamic-cues`: Activa o desactiva las guías automáticas.
     - `POST /api/transport/play-cue?name=...`: Dispara cualquier indicación por su nombre en los in-ears.
   - **Controles en Panel de Operador (`control.html`):** Switch con indicador LED `🎙️ Guías In-Ear: ON` y barra de micro-cues rápidos para el director (`⚠️ Atentos`, `🛑 Corte`, `🔁 Repite`, `Intro`, `Verso`, `Coro`, `Puente`, `Final`).

3. **Luces del Metrónomo Gigantes para Escenario (`musicians.html`):**
   - **Lámparas de Compás de 34px:** Luces aumentadas para permitir lectura clara desde atriles a 1.5–2 metros de distancia con números de pulso (1, 2, 3, 4) bien destacados.
   - **Downbeat Ámbar Brillante:** El tiempo 1 emite un destello dorado expansivo (`#F59E0B`, `box-shadow: 0 0 28px rgba(245, 158, 11, 0.98)`), mientras que los tiempos 2, 3 y 4 parpadean en cian técnico.
   - **Franja Periférica Superior (`#stage-flash-bar`):** Destello sutil en el borde superior de la pantalla visible sin mirar fijamente la tablet. Cumple estrictamente el requerimiento del usuario de **no añadir ningún elemento físico externo al escenario**, resolviendo todo dentro de la pantalla del dispositivo.
   - Paleta OLED 100% negro absoluto (`#000000`) para máximo contraste en tarima y cero brillo residual.

4. **Pruebas y Verificación:**
   - Creado `scripts/test_dynamic_cues.py`: verifica la carga de los 18 WAVs, matching de secciones, inyección en tiempo real en `MultitrackEngine` (peak 1.000 en In-Ear vs 0.000 en FOH) y endpoints REST (100% aprobado).
   - Ejecutado `scripts/test_spontaneous_and_subgroups.py`: 100% aprobado.
   - Servidor en vivo reiniciado (`main.py`) ejecutándose como proceso demonio en el puerto 8000.

---

### 🌐 Direcciones de Acceso en Vivo (Red Local & Localhost):
- **Panel de Control:** `http://localhost:8000/control` (o `http://192.168.0.7:8000/control`)
- **Terminal de Músicos:** `http://192.168.0.7:8000/musicians`
- **Pantalla de Proyección & Loops:** `http://192.168.0.7:8000/projection`
- **Letras Transparentes para OBS Studio:** `http://192.168.0.7:8000/obs`
- **API Guías Dinámicas:** `http://localhost:8000/api/transport/dynamic-cues`

---

### ⚠️ Decisiones técnicas:
- Las guías de voz se sintetizaron de forma local con `Microsoft Helena Desktop` en formato PCM WAV a 44.1 kHz, sin llamadas a APIs externas en la nube.
- La inyección en `cue_mix` suma las muestras al canal de audífonos con un multiplicador de presencia (+2 dB) para que la voz del director/programa corte con claridad a través de la mezcla de monitores de la banda sin saturar.
