# 🎵 Directorio de Pistas Multitrack (`tracks/`)

Este directorio almacena las canciones y sus respectivas pistas de audio separadas (stems).

---

## 📁 Estructura Sugerida para Cada Canción

Cada canción debe organizarse dentro de su propia subcarpeta:

```text
tracks/
├── cuan_grande_es_dios/
│   ├── song.json            # Metadatos, tempo, acordes y letras sincronizadas
│   ├── click.wav            # Pista de metrónomo
│   ├── guide.wav            # Pista de guía vocal hablada ("Intro, 2, 3, 4")
│   ├── drums.wav            # Batería
│   ├── bass.wav             # Bajo
│   ├── guitars.wav          # Guitarras acústicas y eléctricas
│   ├── keys.wav             # Teclados y pianos
│   └── pad.wav              # Colchón o pad ambiental
└── la_bondad_de_dios/
    ├── song.json
    ├── click.wav
    ├── guide.wav
    └── ...
```

---

## 💡 Recomendaciones de Formato de Audio

- **Formato ideal:** WAV o FLAC (PCM 16 o 24 bits, 44100 Hz o 48000 Hz).
- **Formatos comprimidos soportados:** MP3 (320 kbps) u OGG para ahorrar espacio en disco.
- **Importante:** Todos los archivos de audio de una misma canción deben comenzar exactamente en el segundo `0.00` para garantizar alineación de fase perfecta entre todos los instrumentos.
