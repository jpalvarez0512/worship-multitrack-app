# 🎛️ Guía Rápida para el Operador de Cabina de Sonido

**Proyecto:** Worship Multitrack App  
**Uso:** Cabina de Sonido / Equipo de Producción del Templo

---

## 1. Conexión de Audio y Salidas

La aplicación permite dos esquemas de conexión según el equipo disponible en tu iglesia:

### Opción A: Interfaz de Audio Profesional Multicanal (Recomendada)
- Conecta tu interfaz USB (Focusrite, Behringer, PreSonus, etc.) al PC.
- En la app, asigna:
  - **Salidas 1 y 2 (Master L/R):** Conéctalas a los canales de la consola principal (FOH). Contienen las pistas musicales de fondo.
  - **Salida 3 o Auriculares (Cues):** Conéctala al transmisor de monitoreo in-ear de los músicos. Contiene el Click (metrónomo) y la Guía hablada.

### Opción B: Modo División Estéreo (Split Stereo para interfaces de 2 canales)
- Si solo tienes la salida auxiliar de 3.5mm o una interfaz de 2 canales:
  - Activa la casilla **"Modo Split Estéreo"**.
  - **Canal Izquierdo (L):** Contiene solo el Click y la Guía (enviar a monitores in-ear).
  - **Canal Derecho (R):** Contiene la música en mono (enviar a la consola del templo).

---

## 2. Poner en Marcha la Sincronización en Red

1. Conecta la computadora del multitrack a la misma red Wi-Fi o router del templo que usarán los músicos.
2. Inicia la aplicación.
3. Se generará un **Código QR** en la pantalla del PC.
4. Muestra ese código a los músicos para que lo escaneen con sus teléfonos o tablets, o dales el enlace local indicado (ejemplo: `http://192.168.1.50:8080`).

---

## 3. Salida de Proyección (Pantallas del Templo)

1. Conecta la pantalla o proyector secundario mediante cable HDMI.
2. Abre la URL `http://localhost:8080/projection` en tu navegador y arrástrala a la pantalla del proyector.
3. Presiona la tecla `F11` para ponerla a pantalla completa.
4. Si necesitas ocultar la letra temporalmente durante una oración o cuando hable el pastor, presiona el botón **"Ocultar Letra (Blank)"** en el panel de control.
