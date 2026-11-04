# 🏛️ Especificación de Arquitectura de Sistema

**Proyecto:** Worship Multitrack App  
**Versión:** 1.0.0  
**Fecha:** 2026-11-04  
**Elaborado por:** Equipo de Subagentes (`01-lead-architect`)

---

## 1. Visión General del Sistema

El sistema **Worship Multitrack App** está diseñado para resolver la necesidad integral de una iglesia en la administración de alabanza en vivo:
1. **Reproducción de Stems:** Manejo de pistas de audio por canales independientes en un PC principal.
2. **Sincronización a Músicos:** Transmisión en tiempo real de acordes y letras a teléfonos y tablets de los músicos en el escenario.
3. **Proyección para la Congregación:** Envío en tiempo real únicamente de la letra a pantallas, proyectores o sistemas de transmisión (OBS / vMix) sin latencia perceptible.

```
                    ┌──────────────────────────────────────────────┐
                    │               PC ANFITRIÓN                   │
                    │   ┌──────────────────────────────────────┐   │
                    │   │        Motor Multitrack Python       │   │
                    │   │  (sounddevice + numpy + AudioClock)  │   │
                    │   └──────────────────┬───────────────────┘   │
                    │                      │ Sincronización Interna│
                    │   ┌──────────────────▼───────────────────┐   │
                    │   │    Servidor WebSocket / FastAPI      │   │
                    │   └──────────────────┬───────────────────┘   │
                    └──────────────────────┼───────────────────────┘
                                           │ Red Local Wi-Fi (LAN)
                   ┌───────────────────────┴───────────────────────┐
                   ▼                                               ▼
    ┌─────────────────────────────┐                 ┌─────────────────────────────┐
    │    TERMINAL DE MÚSICOS      │                 │    PANTALLA DE PROYECCIÓN   │
    │  (Tablets / Móviles Android)│                 │   (Proyector Templo / OBS)  │
    │  • Acordes en tiempo real   │                 │  • Solo letra de congregación│
    │  • Letra sincronizada       │                 │  • Fondo personalizable     │
    │  • Transposición de tono    │                 │  • Modo pantalla en blanco  │
    │  • Auto-scroll suave        │                 │  • Lower-thirds para stream │
    └─────────────────────────────┘                 └─────────────────────────────┘
```

---

## 2. Los Tres Pilares Funcionales

### Pilar 1: Motor de Audio Multitrack (Python)
- **Carga de Stems:** Lectura en streaming o precarga en memoria RAM de pistas WAV/MP3.
- **Ruteo de Salidas:**
  - Canal Master / FOH: Pistas de acompañamiento musical para el público.
  - Canal In-Ears: Pistas de acompañamiento + Click (Metrónomo) + Guía vocal hablada ("Coro, 2, 3, 4").
- **Reloj Maestro (Master Clock):** Fuente única de verdad temporal basada en la cantidad exacta de samples de audio reproducidos.

### Pilar 2: Terminal de Músicos (Acordes + Letra Sincronizada)
- **Protocolo de Red:** Suscripción al WebSocket `/ws/musicians`.
- **Renderizado Dinámico:** Los acordes se despliegan sobre las sílabas exactas y se transponen instantáneamente al tono deseado.
- **Seguimiento Automático:** El sistema hace scroll automático según avanza la canción, garantizando que el músico nunca tenga que tocar la pantalla con las manos ocupadas en su instrumento.

### Pilar 3: Terminal de Proyección y Streaming
- **Protocolo de Red:** Suscripción al WebSocket `/ws/projection`.
- **Limpieza Total:** Sin acordes, sin marcas de tiempo técnicas, sin cursores.
- **Flexibilidad Visual:** Modo pantalla completa para proyector HDMI y modo transparente (lower-thirds) para transmisiones online en OBS/vMix.

---

## 3. Formato Estándar de Canción (.worship.json)

Cada canción se define en un archivo estructurado que enlaza el audio y el contenido:

```json
{
  "id": "cuan_grande_es_dios",
  "title": "Cuán Grande es Dios",
  "artist": "En Espiritu y En Verdad",
  "tempo_bpm": 76,
  "time_signature": "4/4",
  "original_key": "C",
  "stems": [
    {"name": "Click", "file": "click.wav", "route": "headphones", "volume": 0.8},
    {"name": "Guia", "file": "guide.wav", "route": "headphones", "volume": 0.9},
    {"name": "Bateria", "file": "drums.wav", "route": "master", "volume": 0.85},
    {"name": "Bajo", "file": "bass.wav", "route": "master", "volume": 0.85},
    {"name": "Guitarras", "file": "guitars.wav", "route": "master", "volume": 0.8},
    {"name": "Teclados", "file": "keys.wav", "route": "master", "volume": 0.8}
  ],
  "sections": [
    {"name": "Intro", "start_time": 0.0, "end_time": 12.63},
    {"name": "Verso 1", "start_time": 12.63, "end_time": 37.89},
    {"name": "Coro", "start_time": 37.89, "end_time": 63.15}
  ],
  "lyrics_chords": [
    {
      "section": "Verso 1",
      "start_time": 12.63,
      "end_time": 25.26,
      "musician_view": "[C]El esplendor de un Rey, [Am7]vestido en majestad",
      "projection_view": "El esplendor de un Rey, vestido en majestad"
    },
    {
      "section": "Verso 1",
      "start_time": 25.26,
      "end_time": 37.89,
      "musician_view": "La [F2]tierra alegre esté, la [G]tierra alegre esté",
      "projection_view": "La tierra alegre esté, la tierra alegre esté"
    }
  ]
}
```
