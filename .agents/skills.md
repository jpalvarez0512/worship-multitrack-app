---
title: Catálogo Maestro de Skills Técnicas y de Dominio
project: Worship Multitrack App
version: 1.0.0
last_updated: 2026-11-04
scope: Equipo completo de subagentes de desarrollo
---

# 🧠 Catálogo Maestro de Skills del Equipo (.agents/skills.md)

Este documento define el conjunto de conocimientos técnicos, patrones de diseño, estándares de código y destrezas de dominio musical y tecnológico que todos los agentes del equipo deben dominar y aplicar rigurosamente durante el desarrollo de la aplicación.

---

## 1. Dominio Musical & Culto en Vivo (Church Worship Operations)

- **Manejo de Stems y Multitracks:**
  - Comprensión de pistas separadas: Click (Metrónomo), Guía (Cues hablados: "Intro, 2, 3, 4", "Verso", "Coro"), Batería, Bajo, Guitarras acústicas/eléctricas, Pianos/Sintetizadores, Pads, Voces de apoyo.
  - Ruteo de audio dividido: Salidas mono/estéreo diferenciadas para el FOH (Front of House / Sala principal) vs In-Ears (Monitores de músicos). Los músicos deben escuchar la Guía y el Click sin que estos salgan por los altavoces de la iglesia.
- **Estructura Dinámica de Canciones:**
  - Secciones estándar: `Intro`, `Verso 1`, `Pre-Coro`, `Coro`, `Puente`, `Instrumental`, `Outro`, `Espontáneo / Vamp`.
  - Capacidad para saltos de sección en caliente (hot-jumping) y loops de secciones (ej. repetir el coro o el puente en momentos de ministración).
- **Notación y Acordes:**
  - Formato ChordPro estándar (`[G]Gracia y [D]paz`).
  - Algoritmos de transposición musical (cambio de tonalidad en tiempo real preservando sostenidos/bemoles).
  - Notación cifrada internacional (C, D, E, F, G, A, B) y Sistema de Números de Nashville (1, 4, 5, 6m).

---

## 2. Audio Engineering & DSP en Python

- **Librerías de Audio en Python:**
  - `sounddevice` / `PyAudio` (PortAudio bindings) para reproducción multicanal de ultrabaja latencia (buffers de 64 a 256 samples).
  - `miniaudio` para decodificación rápida de múltiples formatos (WAV, MP3, FLAC, OGG).
  - `numpy` para mezcla en memoria de arreglos de audio (matrices de flotantes de 32 bits), control de ganancia y pan.
- **Sincronización de Audio (Clock Master):**
  - Manejo de un reloj de alta precisión (`time.perf_counter` o `sample_count / sample_rate`) inmune al jitter del garbage collector.
  - Generación interna o playback preciso de Click con firmas de tiempo comunes (4/4, 6/8, 3/4) y tempo (BPM).
  - Detección y manejo de audio underruns (xruns) para evitar clicks o pausas en vivo.

---

## 3. Redes de Tiempo Real & Sincronización LAN (Zero-Configuration)

- **Arquitectura de Servidor Local:**
  - `FastAPI` + `Uvicorn` o `aiohttp` para servir la API de control y la interfaz estática.
  - WebSockets asíncronos para emisión periódica del timestamp maestro (20 a 50 Hz / 50ms interval) a todos los clientes conectados.
- **Protocolo de Sincronización Cliente-Servidor:**
  - Algoritmo simplificado tipo NTP (Network Time Protocol) para compensar el retardo de red entre el PC y los dispositivos móviles.
  - Broadcast de eventos de cambio de sección, play, pause, seek y tempo.
- **Autodescubrimiento en Red Local (LAN):**
  - Implementación de Zeroconf (mDNS / Bonjour) o broadcast UDP en la subred para que las tablets y pantallas encuentren automáticamente el servidor sin escribir direcciones IP manuales.
  - Código QR generado en la pantalla del host para conexión inmediata de los músicos escaneando con la cámara.

---

## 4. Desarrollo Web & UI/UX para Músicos (Terminal Móvil/Tablet)

- **Diseño Adaptativo y Modo Escenario:**
  - Tema de alto contraste (fondo oscuro #121212, tipografía de alta visibilidad para letras en blanco/amarillo y acordes resaltados en azul/cyan brillante).
  - Auto-scroll automático e inteligente sincronizado con los compases y la sección activa.
  - Modos de visualización: Pantalla dividida (Letra + Acordes), Solo Acordes, o Vista de Sección Actual / Siguiente.
- **Optimización para Dispositivos Móviles:**
  - API Wake Lock en navegadores web para evitar que la pantalla del teléfono o tablet se apague durante el servicio.
  - Interfaz táctil ergonómica con controles grandes para cambio de tono (+/- semitonos) y tamaño de fuente.

---

## 5. Módulo de Proyección & Broadcast (Pantalla del Público)

- **Salida de Proyección Limpia (Clean Feed):**
  - Ventana secundaria de pantalla completa (Fullscreen) desacoplada de la interfaz de control.
  - Renderizado exclusivo de las líneas de la letra que corresponden a la estrofa/coro actual.
  - Modo Lower-Thirds (tercios inferiores transparentes) para overlay sobre video en vivo vía HDMI o captura en OBS Studio.
- **Personalización Visual:**
  - Selección de fondos (colores sólidos, gradientes o videos en bucle discretos).
  - Transiciones suaves entre líneas de letra (fade in / fade out configurable).
  - Modo "Blank" / "Clear" instantáneo para ocultar la letra cuando no se requiera.

---

## 6. Empaquetado Multiplataforma (PC & APKs de Android)

- **Distribución en PC:**
  - Scripts modulares de Python con entorno virtual aislado (`venv`).
  - Creación de ejecutables portátiles independientes para Windows usando `PyInstaller` o `Nuitka`.
- **Compilación para Android (APK):**
  - Opciones de arquitectura para el cliente móvil:
    1. **Flet (Flutter + Python):** Permite construir interfaces reactivas en Python y compilar a APK nativo para Android.
    2. **Kivy / Kivymd + Buildozer:** Framework Python multiplataforma nativo para Android.
    3. **Capacitor / TWA (Trusted Web Activity):** Empaquetar el cliente web ultraligero en un archivo APK instalable en cualquier tablet o teléfono Android.
  - Gestión de permisos en Android (Wi-Fi multicast, mantener pantalla encendida, almacenamiento local de caché).

---

## 7. Formatos de Datos & Almacenamiento

- **Estructura del Formato de Canción (.json / .worship):**
  - Metadatos: Título, Artista, Tonalidad Original, BPM, Métrica (4/4, 6/8).
  - Mapeo de Stems: Lista de archivos de audio relativos (`click.wav`, `drums.wav`, `bass.wav`, `keys.wav`, etc.) y volúmenes por defecto.
  - Mapeo de Secciones con Timestamps: Marcadores de tiempo exactos en milisegundos (`intro_start: 0.00`, `verse1_start: 14.50`, etc.).
  - Letra y Acordes sincronizados línea por línea con marcas de tiempo (LRC enriquecido o formato JSON estructurado).

---

## 8. Calidad, Testing & Resiliencia en Vivo

- **Resiliencia ante Desconexiones:**
  - Si un músico pierde la señal Wi-Fi momentáneamente, la app cliente debe reconectarse silenciosamente sin interrumpir la visualización y recalibrar su posición inmediatamente.
- **Consumo Mínimo de Recursos:**
  - Evitar sobrecarga de CPU y memoria en el PC host para garantizar que el motor de audio nunca sufra congelamientos o chasquidos.
  - Pruebas automatizadas de jitter de red y pruebas de estrés con hasta 20 dispositivos conectados simultáneamente en la misma red local.

---

## 9. Continuidad Operativa, Relevos y Control de Versiones Git

- **Protocolo de Relevo (Handover Pattern):**
  - Auditoría sistemática de cambios locales (`git status`, `git diff --stat`).
  - Documentación obligatoria de logros, trabajo en progreso (WIP), bloqueos técnicos y siguiente paso inmediato en `HANDOVER.md`.
- **Estrategia de Ramas y Commits:**
  - Convención de mensajes basada en Conventional Commits: `feat:`, `fix:`, `chore(handover):`, `docs:`, `refactor:`.
  - Integración continua y sincronización con remotos en GitHub garantizando que cada sesión inicie desde un estado limpio y conocido.
