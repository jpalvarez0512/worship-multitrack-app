# 📑 Especificación del Proyecto: Worship Multitrack App

## 1. Resumen Ejecutivo
**Worship Multitrack App** es una plataforma integral para iglesias diseñada para ejecutarse como un script/servicio en Python en la computadora principal del templo. Permite reproducir pistas de audio separadas (multitracks), sincronizar la visualización de acordes y letras en las pantallas de los músicos (tablets/smartphones) y enviar automáticamente la letra sincronizada sin acordes a los proyectores o pantallas de la congregación.

---

## 2. Requerimientos Funcionales

### RF-01: Reproducción y Mezcla Multipista
- Carga de pistas separadas (stems): Guía, Metrónomo (Click), Batería, Bajo, Guitarras, Teclados, Pistas ambientales (Pads) y Voces de apoyo.
- Fader individual de volumen por stem (0% a 100%), botón Mute y Solo.
- Ruteo independiente:
  - Salida Estéreo Principal (FOH / Sala): Instrumentación musical sin Click ni Guía.
  - Salida de Monitoreo (In-Ears Músicos): Instrumentación + Click + Guía vocal.

### RF-02: Reloj de Sincronización Maestro
- Reloj central en Python basado en frames de audio para prevenir cualquier desincronización o jitter acumulativo.
- Transmisión en tiempo real de la posición de la canción a la red local vía WebSockets.

### RF-03: Pantalla para Músicos (Terminal Escenario)
- Despliegue de letra y acordes sincronizados compás por compás.
- Desplazamiento automático (*auto-scroll*) para mantener la estrofa actual visible sin intervención manual.
- Transpositor dinámico de tonalidad en tiempo real (+/- semitonos).
- Modo de visualización de alto contraste optimizado para escenario oscuro.

### RF-04: Pantalla de Proyección (Templo y Transmisión)
- Visualización limpia solo de la letra (sin acordes, compases ni datos de audio).
- Salida a pantalla completa para segundo monitor o proyector HDMI.
- Modo *Lower-Thirds* transparente para superposición en OBS Studio / vMix.
- Botones de acción rápida: "Ocultar Texto", "Pantalla Negra", "Mostrar Fondo/Logo".

### RF-05: Conectividad y Cero Configuración (Zero-Conf)
- Servidor local accesible por Wi-Fi mediante IP local o nombre de host mDNS.
- Generación de código QR en la aplicación principal para conexión instantánea desde teléfonos y tablets.

### RF-06: Distribución Multiplataforma
- Ejecución en PC (Windows) como script en Python o ejecutable portable.
- Aplicación empaquetada en formato APK para instalación directa en dispositivos Android.

---

## 3. Requerimientos No Funcionales

- **Latencia de Red:** La sincronización entre el audio y la pantalla no debe superar los 50 milisegundos en red local Wi-Fi.
- **Resiliencia:** Si un dispositivo móvil se desconecta y reconecta, debe sincronizarse inmediatamente con la posición actual sin requerir intervención manual.
- **Rendimiento:** Consumo de CPU menor al 20% en un procesador Intel Core i5 / AMD Ryzen 5 estándar durante la reproducción simultánea de 12 canales de audio.

---

## 4. Stack Tecnológico

- **Lenguaje:** Python 3.10+
- **Motor de Audio:** `sounddevice`, `numpy`, `miniaudio`, `pyaudio`
- **Servidor y API:** `FastAPI`, `Uvicorn`, `WebSockets`
- **Frontend Músicos & Proyección:** HTML5, CSS3 moderno, JavaScript vanilla o framework reactivo ligero con soporte offline y Screen Wake Lock API.
- **Empaquetado Móvil:** Flet (Python + Flutter) o contenedor APK nativo (Capacitor/WebView) con `buildozer` / `gradle`.
