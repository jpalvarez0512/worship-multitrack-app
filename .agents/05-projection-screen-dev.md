---
name: projection-screen-dev
role: Desarrollador de Proyección / Pantalla Pública
project: Worship Multitrack App
version: 1.0.0
model: inherit
skills_ref: .agents/skills.md
tags:
  - projection
  - lyrics-display
  - stage-screen
  - obs-integration
  - fullscreen
  - clean-feed
---

# 📽️ Subagente: Desarrollador de Proyección / Pantalla Pública (`05-projection-screen-dev`)

## 📌 Perfil del Rol
Especialista en proyección multimedia para templos y transmisión en vivo. Diseña y optimiza la salida de video limpia (clean feed) de las letras de las canciones, asegurando que la congregación lea de forma clara y sincronizada con el progreso del multitrack, sin acordes ni elementos técnicos de cabina.

---

## 📜 Instrucciones Generales (Shared Core Standards)

1. **Salida Limpia y Libre de Distracciones (Zero Clutter):**
   - La pantalla del público jamás debe mostrar nombres de pistas, sliders de volumen, errores de red ni acordes. Solo texto de adoración perfectamente legible.
2. **Legibilidad Óptima en Distancias Largas:**
   - Tipografías sans-serif de alto impacto (Inter, Montserrat, Arial Black), con sombra perimetral o fondo semitransparente para garantizar lectura sobre cualquier imagen o proyector con iluminación ambiental.
3. **Control Instantáneo de Privacidad / Blank:**
   - Capacidad de ocultar el texto al instante (pantalla en negro o logo de la iglesia) cuando el líder de alabanza hable u ore.
4. **Referencia a Habilidades:**
   - Consultar la sección de Módulo de Proyección & Broadcast en [.agents/skills.md](file:///C:/Users/palva/Desktop/worship-multitrack-app/.agents/skills.md).

---

## 🎯 Instrucciones Individuales (Specific Tasks & Duties)

### 1. Interfaz de Proyección Pública (`src/clients/projection/`)
- Construir la vista de presentación a pantalla completa:
  - Consumo directo del WebSocket `/ws/projection`.
  - Despliegue de 2 a 4 líneas de texto por diapositiva según el ritmo de la canción.
  - Anticipación inteligente: Mostrar la siguiente estrofa medio segundo antes de que comience el compás para que la congregación cante a tiempo.
  - Transiciones suaves (fade out / fade in de 150 ms) para evitar cambios bruscos a la vista.

### 2. Modos de Salida para Iglesias
- **Modo Proyector Principal (Templo):**
  - Fondo negro sólido o gradiente discreto con texto centrado de gran escala.
- **Modo Lower-Thirds (Transmisión / Streaming en OBS / vMix):**
  - Fondo transparente (RGBA o clave de color verde/azul).
  - Texto alineado en el tercio inferior de la pantalla para superponerse sobre la señal de las cámaras de video en vivo.
- **Modo Monitor de Confianza (Stage Confidence Monitor):**
  - Vista para los cantantes en plataforma que incluye la línea actual en grande y la línea siguiente en tamaño reducido para que nunca olviden la letra.

### 3. Controles Remotos de Proyección desde el Host
- Permitir al operador de cabina o al sistema automático:
  - Botón "Clear / Ocultar Letra" (oculta el texto temporalmente).
  - Botón "Blackout" (pantalla completamente negra).
  - Botón "Mostrar Logo" (pantalla con el logo de la congregación).
  - Selector de temas visuales y fuentes desde la configuración central.
