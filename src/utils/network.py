"""
Utilidades de Red Local (LAN) y Generación de Códigos QR
Subagente responsable: 03-network-sync-engineer
"""

import io
import socket
from typing import Optional
import qrcode


def get_local_ip() -> str:
    """
    Detecta la dirección IP local del equipo dentro de la red Wi-Fi / Ethernet local.
    Usa un socket UDP simulado hacia una IP externa (sin enviar tráfico real)
    para determinar qué interfaz de red tiene ruta activa hacia la LAN/Internet.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No se envía tráfico real, solo se resuelve la interfaz de salida
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_connection_url(port: int = 8000, path: str = "") -> str:
    """Devuelve la URL completa para acceder al servidor desde otros dispositivos de la LAN."""
    ip = get_local_ip()
    cleaned_path = "/" + path.lstrip("/") if path else ""
    return f"http://{ip}:{port}{cleaned_path}"


def print_ascii_qr(data: str) -> None:
    """Imprime un código QR en la consola de texto para escaneo rápido con la cámara."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


def generate_qr_svg_or_ascii(data: str) -> str:
    """Genera representación del QR en texto ASCII formateado."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    f = io.StringIO()
    qr.print_ascii(out=f, invert=True)
    return f.getvalue()
