"""
Módulo de Extracción y Caché de Formas de Onda (Waveforms)
Worship Multitrack Live
Permite generar y entregar perfiles de amplitud de audio para visualización
interactiva y edición de marcadores de secciones en la consola central.
"""

import json
import math
import os
from typing import Dict, List, Optional
import numpy as np

from src.audio.stem import StemTrack


def generate_waveform_peaks(audio_data: np.ndarray, num_points: int = 600) -> List[float]:
    """Reduce una matriz de audio estéreo a un array de picos normalizados entre 0.0 y 1.0."""
    if len(audio_data) == 0:
        return [0.05] * num_points

    if audio_data.ndim > 1:
        mono = np.max(np.abs(audio_data), axis=1)
    else:
        mono = np.abs(audio_data)

    total_len = len(mono)
    chunk_size = max(1, total_len // num_points)
    num_chunks = total_len // chunk_size
    if num_chunks == 0:
        return [0.1] * num_points

    trimmed = mono[: num_chunks * chunk_size].reshape(num_chunks, chunk_size)
    peaks = np.max(trimmed, axis=1)

    if len(peaks) < num_points:
        peaks = np.pad(peaks, (0, num_points - len(peaks)))
    else:
        peaks = peaks[:num_points]

    max_val = float(np.max(peaks))
    if max_val > 0.0001:
        peaks = peaks / max_val
    else:
        peaks = np.full(num_points, 0.05, dtype=np.float32)

    return [round(float(p), 3) for p in peaks]


def get_song_waveform(folder_path: str, max_points: int = 600) -> Dict:
    """
    Obtiene o calcula el perfil de forma de onda de una canción.
    Utiliza caché en 'waveform.json' dentro de la carpeta de la canción.
    """
    cache_path = os.path.join(folder_path, "waveform.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "peaks" in data and len(data["peaks"]) > 0:
                    return data
        except Exception:
            pass

    # Si no hay caché, buscar pistas de audio en stems/ o raíz
    audio_files = []
    stems_dir = os.path.join(folder_path, "stems")
    if os.path.isdir(stems_dir):
        for f in sorted(os.listdir(stems_dir)):
            if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a")):
                audio_files.append(os.path.join(stems_dir, f))

    if not audio_files:
        for f in sorted(os.listdir(folder_path)):
            if f.lower().endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a")):
                audio_files.append(os.path.join(folder_path, f))

    # Seleccionar preferentemente un stem instrumental que no sea solo click ni guía
    chosen_file = None
    for p in audio_files:
        low = os.path.basename(p).lower()
        if not any(k in low for k in ("click", "clic", "metronomo", "guia", "guide")):
            chosen_file = p
            break
    if not chosen_file and audio_files:
        chosen_file = audio_files[0]

    peaks = []
    duration = 0.0
    if chosen_file and os.path.exists(chosen_file):
        try:
            stem = StemTrack.load_from_file(chosen_file)
            peaks = generate_waveform_peaks(stem.audio_data, num_points=max_points)
            duration = stem.duration_seconds
        except Exception as ex:
            print(f"[WAVEFORM] Error generando forma de onda para {chosen_file}: {ex}")

    if not peaks:
        # Picos sinteticos agradables por defecto si no hay archivos aun
        peaks = [round(0.1 + 0.5 * abs(math.sin(i * 0.05)), 3) for i in range(max_points)]
        duration = 180.0

    result = {
        "peaks": peaks,
        "duration": round(duration, 2),
        "points": len(peaks),
    }

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
    except Exception:
        pass

    return result
