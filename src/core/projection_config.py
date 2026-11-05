"""
Configuración Persistente de Proyección: Fondos, Color/Sombra de Letras y Anticipación
"""

import json
import os
import shutil
import threading
from typing import BinaryIO, List, Optional
from src.core.song_loader import COPY_CHUNK_SIZE, sanitize_filename


BACKGROUND_MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".mp4", ".webm", ".mov", ".m4v",
}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}

PRESET_BACKGROUNDS = [
    {"id": "loop-aurora", "label": "🎬 Loop: Aurora Celestial", "kind": "preset"},
    {"id": "loop-particles", "label": "🎬 Loop: Destellos Dorados", "kind": "preset"},
    {"id": "ocean", "label": "Azul Noche", "kind": "preset"},
    {"id": "worship-purple", "label": "Púrpura Adoración", "kind": "preset"},
    {"id": "warm-gold", "label": "Luz de Altar", "kind": "preset"},
    {"id": "emerald", "label": "Agua Viva", "kind": "preset"},
    {"id": "black", "label": "Negro Puro", "kind": "preset"},
]

DEFAULT_PROJECTION_SETTINGS = {
    "background": "loop-aurora",
    "dim_opacity": 0.30,
    "lead_seconds": 1.5,
    "text_color": "#FFE600",
    "lower_thirds": False,
}


class ProjectionConfigManager:
    """Gestiona ajustes visuales, anticipación temporal y fondos personalizados de proyección."""

    def __init__(self, config_dir: str):
        self.config_dir = os.path.abspath(config_dir)
        self.settings_file = os.path.join(self.config_dir, "projection_settings.json")
        self.backgrounds_dir = os.path.join(self.config_dir, "backgrounds")
        os.makedirs(self.backgrounds_dir, exist_ok=True)
        self._lock = threading.RLock()
        self._settings = self._load()

    def _load(self) -> dict:
        merged = dict(DEFAULT_PROJECTION_SETTINGS)
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        merged.update(data)
            except Exception:
                pass
        return merged

    def _save(self) -> None:
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=2, ensure_ascii=False)

    def get_settings(self) -> dict:
        with self._lock:
            s = dict(self._settings)
        bg = s.get("background", "ocean")
        s["background_url"] = None
        s["background_is_video"] = False
        if isinstance(bg, str) and bg.startswith("custom:"):
            fname = bg.split("custom:", 1)[1]
            s["background_url"] = f"/backgrounds/{fname}"
            s["background_is_video"] = os.path.splitext(fname)[1].lower() in VIDEO_EXTENSIONS
        return s

    @property
    def lead_seconds(self) -> float:
        with self._lock:
            return float(self._settings.get("lead_seconds", 1.5))

    def update_settings(
        self,
        background: Optional[str] = None,
        dim_opacity: Optional[float] = None,
        lead_seconds: Optional[float] = None,
        text_color: Optional[str] = None,
        lower_thirds: Optional[bool] = None,
    ) -> dict:
        with self._lock:
            if background is not None:
                self._settings["background"] = str(background)
            if dim_opacity is not None:
                self._settings["dim_opacity"] = round(max(0.0, min(0.85, float(dim_opacity))), 2)
            if lead_seconds is not None:
                self._settings["lead_seconds"] = round(max(0.0, min(5.0, float(lead_seconds))), 2)
            if text_color is not None and text_color.strip():
                self._settings["text_color"] = text_color.strip()
            if lower_thirds is not None:
                self._settings["lower_thirds"] = bool(lower_thirds)
            self._save()
        return self.get_settings()

    def list_backgrounds(self) -> List[dict]:
        items = list(PRESET_BACKGROUNDS)
        if os.path.isdir(self.backgrounds_dir):
            for fname in sorted(os.listdir(self.backgrounds_dir)):
                ext = os.path.splitext(fname)[1].lower()
                if ext in BACKGROUND_MEDIA_EXTENSIONS:
                    items.append({
                        "id": f"custom:{fname}",
                        "filename": fname,
                        "label": os.path.splitext(fname)[0],
                        "kind": "video" if ext in VIDEO_EXTENSIONS else "image",
                        "url": f"/backgrounds/{fname}",
                    })
        return items

    def save_background_file(self, original_name: str, stream: BinaryIO) -> dict:
        safe_name = sanitize_filename(original_name)
        ext = os.path.splitext(safe_name)[1].lower()
        if ext not in BACKGROUND_MEDIA_EXTENSIONS:
            raise ValueError(
                f"Formato no soportado ({ext}). Usa video loop (.mp4, .webm, .mov) o imagen (.jpg, .png, .webp, .gif)."
            )
        dest = os.path.join(self.backgrounds_dir, safe_name)
        with open(dest, "wb") as out:
            shutil.copyfileobj(stream, out, COPY_CHUNK_SIZE)
        return {
            "id": f"custom:{safe_name}",
            "filename": safe_name,
            "label": os.path.splitext(safe_name)[0],
            "kind": "video" if ext in VIDEO_EXTENSIONS else "image",
            "url": f"/backgrounds/{safe_name}",
        }

    def delete_background_file(self, filename: str) -> None:
        safe_name = sanitize_filename(filename)
        path = os.path.join(self.backgrounds_dir, safe_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Fondo no encontrado: {filename}")
        os.remove(path)
        with self._lock:
            if self._settings.get("background") == f"custom:{safe_name}":
                self._settings["background"] = "loop-aurora"
                self._save()
