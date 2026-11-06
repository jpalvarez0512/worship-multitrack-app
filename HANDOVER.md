# 🔄 Último Handover (Relevo)
- **Fecha:** 2026-11-06 16:47
- **Desarrollador / Cuenta:** jpalvarez0512
- **Rama activa:** main (Sincronizado con origin/main en GitHub)

### ✅ Completado en esta sesión:
1. **Aviso Anticipado Obligatorio de 1 Compás al Cambiar de Sección con Conteo Rítmico:**
   - **Requisito cumplido:** Si el director o usuario solicita un salto cuantizado a otra sección (incluso si se presiona en el último click del compás en curso), el cambio **nunca es tropezado ni abrupto**.
   - **Compás de Aviso Musical (`build_transition_cue` en `src/audio/cue_manager.py`):**
     - Sintetiza dinámicamente un compás rítmico completo (ej. 88,200 muestras para 120 BPM 4/4) adaptado exactamente al BPM de la canción activa.
     - Ubica la voz en el Tiempo 1 diciendo el nombre de la sección (`"Coro"`, `"Puente"`, etc.) seguido de los tiempos rítmicos: tiempo 2 (`"dos"`), tiempo 3 (`"tres"`) y tiempo 4 (`"cuatro"`).
   - **Programación de 2 Compases en `MultitrackEngine` (`src/audio/engine.py`):**
     - `_jump_lead_bar_frame`: Compás donde se inyecta la guía de aviso rítmico en el canal In-Ear (`cue_mix`).
     - `_jump_target_bar_frame`: Compás donde se realiza la transición musical isopotente hacia la sección de destino.
     - Si se solicita el cambio mientras la pista está pausada, el seek es instantáneo para agilidad en soundcheck.
     - Cancelación segura mediante `cancel_scheduled_jump()` limpiando ambos punteros de compás.

2. **Erradicación Total de Emojis y Rediseño Minimalista Pro DAW (Anti-IA):**
   - **Cero Emojis:** Se eliminaron el 100% de emojis en todo el código HTML, CSS, JavaScript y notificaciones (`control.html`, `musicians.html`, `projection.html`, `obs.html`).
   - **Estética Técnica de DAW Profesional (Ableton Live 12 / Bitwig Studio / Pro Tools):**
     - Fondo grafito técnico neutro (`#131417`), tarjetas planas (`#1b1c21`) con bordes nítidos de 1px (`#282a32`), sin brillos plásticos ni degradados 3D exagerados.
     - Tipografía monoespaciada/técnica de alta densidad con etiquetas funcionales en mayúsculas micro-espaciadas: `SETLISTS`, `PLAY`, `PAUSE`, `STOP`, `LOOP SECCIÓN`, `GUÍAS IN-EAR: ON`, `ATENTOS`, `CORTE`, `REPITE`, `+ PISTAS`, `PANTALLA NEGRA`, `OCULTAR TEXTO`.
     - Badges de ruteo sobrios: `[CUE]`, `[FOH]`, `[AMBOS]`.

3. **Luces de Metrónomo Gigantes de Alta Visibilidad para Escenario (`musicians.html`):**
   - Lámparas de pulso aumentadas a **52px x 52px** con números de compás grandes (`1.35rem`, font-weight 900).
   - Downbeat ámbar de alta luminosidad en el pulso 1 y cian técnico en los pulsos 2, 3 y 4.
   - Borde superior de destello de pulso periférico en pantalla (`#stage-flash-bar`) sin requerir ningún hardware externo en tarima.

4. **Pruebas y Verificación:**
   - `scripts/test_dynamic_cues.py`: 100% aprobado (verificación de compás de conteo a 88,200 muestras y ruteo a Split Stereo).
   - `scripts/test_spontaneous_and_subgroups.py`: 100% aprobado (verificación de saltos cuantizados con compás de aviso, bucle continuo y auto-play de medleys).
   - Servidor demonio de FastAPI/Uvicorn reiniciado y operativo en el puerto 8000.

---

### 🌐 Direcciones de Acceso en Vivo (Red Local & Localhost):
- **Panel de Control:** `http://localhost:8000/control` (o `http://192.168.0.7:8000/control`)
- **Terminal de Músicos:** `http://192.168.0.7:8000/musicians`
- **Pantalla de Proyección & Loops:** `http://192.168.0.7:8000/projection`
- **Letras Transparentes para OBS Studio:** `http://192.168.0.7:8000/obs`
- **API Guías Dinámicas:** `http://localhost:8000/api/transport/dynamic-cues`

---

### ⚠️ Decisiones técnicas:
- Las guías de voz y conteo son 100% locales en formato PCM WAV (44.1 kHz).
- En saltos espontáneos, el compás de aviso obligatorio previene confusiones en la banda y otorga tiempo musical exacto para entrar al unísono.
