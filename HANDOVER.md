# 🔄 Último Handover (Relevo)
- **Fecha:** 2026-11-04 16:56
- **Desarrollador / Cuenta:** jpalvarez0512
- **Rama activa:** main (Sincronizado con origin/main en GitHub)

### ✅ Completado en esta sesión:
- Implementación completa del motor de audio multitrack en tiempo real en `src/audio/`:
  - `src/audio/stem.py`: Manejo y carga de stems, normalización float32, balance, volumen, mute, solo y asignación de ruteo (`master` vs `cue`).
  - `src/audio/engine.py`: Motor de mezcla de baja latencia con `sounddevice` y `numpy`, soporte de ruteo estéreo dividido (`SPLIT_STEREO` L=Monitores/Click/Guía, R=Sala/FOH) y normal, controles de transporte (play, pause, stop, seek) y reloj maestro con callbacks periódicos a 25 Hz.
  - `src/audio/synthetic.py`: Generador de pistas sintéticas (metrónomo/click y tonos de instrumentos) para pruebas sin depender de archivos de audio externos.
- Creación y ejecución exitosa del script de diagnóstico y validación en `scripts/test_engine.py`.
- Solución de concurrencia y prevención de bloqueos entre el callback de PortAudio/WASAPI y los controles de transporte mediante `threading.RLock()`.

### 🚧 Trabajo en progreso (WIP):
- Módulo de sincronización en red y servidor WebSocket en `src/server/` para enviar la posición del reloj maestro, cambios de compás, letras y acordes a los dispositivos clientes (teléfonos, tablets y proyector).

### ⚠️ Decisiones técnicas o bloqueos:
- Modo `SPLIT_STEREO` probado y verificado: el canal izquierdo transporta la mezcla de auriculares (click + guías habladas), mientras el canal derecho envía la música limpia a la consola principal de sala.
- Dependencias de audio instaladas y verificadas en el entorno virtual `.venv` (`sounddevice`, `soundfile`, `numpy`).

### 🎯 Siguiente paso prioritario:
- Implementar el servidor local ligero con `FastAPI` y `WebSockets` en `src/server/` que escuche los callbacks de `MultitrackEngine` y emita el estado a los clientes conectados, con detección de IP local y generación de código QR para conexión instantánea de músicos.
