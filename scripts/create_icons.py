"""
Generador de Íconos PWA en PNG y SVG con Python Standard Library (sin dependencias externas).
"""
import os
import struct
import sys
import zlib

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def create_png(width: int, height: int, output_path: str):
    # Generar imagen RGBA: fondo oscuro (#0b1329) con acento cian (#38bdf8) y corona/onda
    raw = bytearray()
    cx, cy = width / 2.0, height / 2.0
    r_max = width / 2.2

    for y in range(height):
        raw.append(0)  # Filter type 0 (None)
        for x in range(width):
            dx = x - cx
            dy = y - cy
            dist = (dx * dx + dy * dy) ** 0.5

            if dist > r_max:
                # Transparente fuera del círculo
                raw.extend([0, 0, 0, 0])
            else:
                # Gradiente de fondo #070b19 a #1e293b
                grad = (y / height)
                r = int(7 + grad * 25)
                g = int(11 + grad * 35)
                b = int(25 + grad * 55)
                a = 255

                # Dibujar ondas multitrack / barra central
                # Barra 1
                if abs(x - cx * 0.6) < width * 0.04 and abs(y - cy) < height * 0.25:
                    r, g, b = 56, 189, 248  # #38bdf8
                # Barra 2 (Central alta)
                elif abs(x - cx) < width * 0.045 and abs(y - cy) < height * 0.38:
                    r, g, b = 250, 204, 21  # #facc15 (dorado worship)
                # Barra 3
                elif abs(x - cx * 1.4) < width * 0.04 and abs(y - cy) < height * 0.28:
                    r, g, b = 56, 189, 248  # #38bdf8
                # Barra 4
                elif abs(x - cx * 1.7) < width * 0.035 and abs(y - cy) < height * 0.15:
                    r, g, b = 96, 165, 250
                # Barra 0
                elif abs(x - cx * 0.3) < width * 0.035 and abs(y - cy) < height * 0.15:
                    r, g, b = 96, 165, 250

                raw.extend([r, g, b, a])

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    png_data = bytearray(b"\x89PNG\r\n\x1a\n")
    # IHDR
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png_data.extend(chunk(b"IHDR", ihdr))
    # IDAT
    compressed = zlib.compress(bytes(raw), level=9)
    png_data.extend(chunk(b"IDAT", compressed))
    # IEND
    png_data.extend(chunk(b"IEND", b""))

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(png_data)


def create_svg(output_path: str):
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0b1329"/>
      <stop offset="100%" stop-color="#1e293b"/>
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#facc15"/>
      <stop offset="100%" stop-color="#eab308"/>
    </linearGradient>
  </defs>
  <circle cx="256" cy="256" r="240" fill="url(#bg)" stroke="#38bdf8" stroke-width="12"/>
  <rect x="96" y="200" width="36" height="112" rx="18" fill="#60a5fa"/>
  <rect x="160" y="140" width="36" height="232" rx="18" fill="#38bdf8"/>
  <rect x="238" y="80" width="36" height="352" rx="18" fill="url(#accent)"/>
  <rect x="316" y="130" width="36" height="252" rx="18" fill="#38bdf8"/>
  <rect x="380" y="190" width="36" height="132" rx="18" fill="#60a5fa"/>
</svg>"""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_content)


if __name__ == "__main__":
    icons_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "icons"))
    create_png(192, 192, os.path.join(icons_dir, "icon-192.png"))
    create_png(512, 512, os.path.join(icons_dir, "icon-512.png"))
    create_svg(os.path.join(icons_dir, "icon.svg"))
    print(f"✓ Íconos PWA generados con éxito en {icons_dir}")
