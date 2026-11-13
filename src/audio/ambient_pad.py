"""
Módulo Generador de Pads Ambientales Continuos y Asistencia de Modulación
Worship Multitrack Live
Permite generar colchones armónicos cálidos para los 12 tonos cromáticos,
manteniendo una atmósfera continua durante la ministración, oración o transiciones,
con crossfades armónicos isopotentes al modular de tono.
"""

import math
from typing import Dict, Optional, Tuple
import numpy as np


# Frecuencias fundamentales de la octava 3 (Hz) para pads de adoración
NOTE_FREQUENCIES: Dict[str, float] = {
    "C": 130.81,
    "C#": 138.59,
    "DB": 138.59,
    "D": 146.83,
    "D#": 155.56,
    "EB": 155.56,
    "E": 164.81,
    "F": 174.61,
    "F#": 185.00,
    "GB": 185.00,
    "G": 196.00,
    "G#": 207.65,
    "AB": 207.65,
    "A": 220.00,
    "A#": 233.08,
    "BB": 233.08,
    "B": 246.94,
}

CANONICAL_KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def canonicalize_key(key: str) -> str:
    """Normaliza cualquier denominación de tono (ej. Db -> C#, sol -> G)."""
    k = (key or "C").strip().upper()
    # Mapeo en español
    es_map = {
        "DO": "C", "DO#": "C#", "REB": "C#",
        "RE": "D", "RE#": "D#", "MIB": "D#",
        "MI": "E",
        "FA": "F", "FA#": "F#", "SOLB": "F#",
        "SOL": "G", "SOL#": "G#", "LAB": "G#",
        "LA": "A", "LA#": "A#", "SIB": "A#",
        "SI": "B"
    }
    if k in es_map:
        return es_map[k]
    if k in ("DB", "C#"):
        return "C#"
    if k in ("EB", "D#"):
        return "D#"
    if k in ("GB", "F#"):
        return "F#"
    if k in ("AB", "G#"):
        return "G#"
    if k in ("BB", "A#"):
        return "A#"
    if k in NOTE_FREQUENCIES:
        return k
    return "C"


class AmbientPadManager:
    """
    Administra la síntesis, reproducción en bucle continuo y modulación cruzada
    de pads ambientales para culto en vivo.
    """

    def __init__(self, sample_rate: int = 44100, loop_duration: float = 12.0):
        self.sample_rate = sample_rate
        self.loop_duration = loop_duration
        self.loop_frames = int(loop_duration * sample_rate)

        self.is_active: bool = False
        self.volume: float = 0.55
        self.current_key: str = "C"
        self.target_key: Optional[str] = None

        # Caché de bucles en memoria para cada tono
        self._pad_cache: Dict[str, np.ndarray] = {}

        # Posiciones de reproducción en las matrices de audio
        self._current_pos: int = 0
        self._target_pos: int = 0

        # Control de modulación y fundido cruzado (crossfade)
        self._crossfade_len: int = int(4.0 * sample_rate)  # 4 segundos por defecto
        self._crossfade_pos: int = 0
        self._is_modulating: bool = False

    def generate_pad_loop(self, key: str) -> np.ndarray:
        """
        Sintetiza un bucle estéreo continuo de pad ambiental cálido (Worship Drone Pad).
        Usa estructura abierta 1-5-8-9 sin tercera para adaptarse a canciones mayores y menores.
        Aplica ligero detune estéreo y modulación lenta para dar aire y movimiento analógico.
        """
        canon_key = canonicalize_key(key)
        if canon_key in self._pad_cache:
            return self._pad_cache[canon_key]

        f0 = NOTE_FREQUENCIES.get(canon_key, 130.81)
        sr = self.sample_rate
        n_samples = self.loop_frames
        t = np.linspace(0, self.loop_duration, n_samples, endpoint=False, dtype=np.float32)

        # 1. Componentes armónicos (Fundamental, Sub-octava, Quinta, Octava, Novena/Segunda)
        # Ondas sinusoidales con ligeros armónicos suaves para emular filtro analógico cálido
        # Canal Izquierdo y Derecho con micro-desafinación (Stereo Detune) para amplitud
        detune_l = 0.9988
        detune_r = 1.0012

        # LFO lento para respiración natural del pad (0.12 Hz)
        lfo = 0.85 + 0.15 * np.sin(2 * np.pi * 0.12 * t)

        # Capa 1: Sub-octava profunda (f0 / 2)
        sub_l = np.sin(2 * np.pi * (f0 * 0.5 * detune_l) * t) * 0.45
        sub_r = np.sin(2 * np.pi * (f0 * 0.5 * detune_r) * t) * 0.45

        # Capa 2: Fundamental con cuerpo cálido (f0)
        fund_l = (np.sin(2 * np.pi * (f0 * detune_l) * t) + 0.25 * np.sin(4 * np.pi * (f0 * detune_l) * t)) * 0.50
        fund_r = (np.sin(2 * np.pi * (f0 * detune_r) * t) + 0.25 * np.sin(4 * np.pi * (f0 * detune_r) * t)) * 0.50

        # Capa 3: Quinta justa (f0 * 1.5) - Da el espacio armónico neutral para mayor y menor
        fifth_l = (np.sin(2 * np.pi * (f0 * 1.5 * detune_l) * t) + 0.15 * np.sin(4 * np.pi * (f0 * 1.5 * detune_l) * t)) * 0.40
        fifth_r = (np.sin(2 * np.pi * (f0 * 1.5 * detune_r) * t) + 0.15 * np.sin(4 * np.pi * (f0 * 1.5 * detune_r) * t)) * 0.40

        # Capa 4: Octava superior y brillo sutil (f0 * 2.0 y f0 * 3.0)
        high_l = (0.20 * np.sin(2 * np.pi * (f0 * 2.0 * detune_l) * t) + 0.10 * np.sin(2 * np.pi * (f0 * 3.0 * detune_l) * t))
        high_r = (0.20 * np.sin(2 * np.pi * (f0 * 2.0 * detune_r) * t) + 0.10 * np.sin(2 * np.pi * (f0 * 3.0 * detune_r) * t))

        # Suma y modulación LFO
        ch_l = (sub_l + fund_l + fifth_l + high_l) * lfo
        ch_r = (sub_r + fund_r + fifth_r + high_r) * lfo

        # Enlace suave de extremos (Seamless Loop Crossfade en los últimos 0.5s)
        fade_samples = int(0.5 * sr)
        fade_env = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0, 1, fade_samples, dtype=np.float32)))
        ch_l[:fade_samples] = ch_l[:fade_samples] * fade_env + ch_l[-fade_samples:] * (1.0 - fade_env)
        ch_r[:fade_samples] = ch_r[:fade_samples] * fade_env + ch_r[-fade_samples:] * (1.0 - fade_env)

        # Normalización suave de pico a -6 dBFS (0.5)
        peak = max(np.max(np.abs(ch_l)), np.max(np.abs(ch_r)), 1e-4)
        ch_l = (ch_l / peak) * 0.50
        ch_r = (ch_r / peak) * 0.50

        stereo_pad = np.column_stack((ch_l, ch_r)).astype(np.float32)
        self._pad_cache[canon_key] = stereo_pad
        return stereo_pad

    def activate(self, key: Optional[str] = None, volume: Optional[float] = None) -> None:
        """Enciende el pad continuo en el tono indicado."""
        if key:
            self.current_key = canonicalize_key(key)
        if volume is not None:
            self.volume = max(0.0, min(1.5, float(volume)))

        self.generate_pad_loop(self.current_key)
        self.target_key = None
        self._is_modulating = False
        self._current_pos = 0
        self.is_active = True

    def deactivate(self) -> None:
        """Apaga el pad continuo."""
        self.is_active = False
        self.target_key = None
        self._is_modulating = False

    def modulate_to(self, new_key: str, crossfade_seconds: float = 4.0) -> Tuple[str, str]:
        """
        Inicia una modulación armónica suave hacia un nuevo tono.
        Retorna (tono_origen, tono_destino).
        """
        canon_new = canonicalize_key(new_key)
        if not self.is_active:
            self.activate(canon_new)
            return (canon_new, canon_new)

        if canon_new == self.current_key and not self._is_modulating:
            return (self.current_key, self.current_key)

        from_key = self.current_key
        self.target_key = canon_new
        self.generate_pad_loop(self.target_key)
        self._crossfade_len = max(int(0.5 * self.sample_rate), int(crossfade_seconds * self.sample_rate))
        self._crossfade_pos = 0
        self._target_pos = 0
        self._is_modulating = True
        return (from_key, canon_new)

    def set_volume(self, volume: float) -> None:
        """Ajusta el volumen de ganancia del pad."""
        self.volume = max(0.0, min(1.5, float(volume)))

    def get_slice(self, frames: int) -> np.ndarray:
        """
        Extrae un bloque de audio de 'frames' muestras aplicando el bucle continuo
        y el crossfade isopotente si hay una modulación en curso.
        """
        if not self.is_active or self.volume <= 0.001:
            return np.zeros((frames, 2), dtype=np.float32)

        cur_buf = self.generate_pad_loop(self.current_key)
        cur_len = len(cur_buf)
        out = np.zeros((frames, 2), dtype=np.float32)

        # 1. Extraer audio del tono actual respetando el bucle
        written = 0
        while written < frames:
            avail = cur_len - self._current_pos
            chunk = min(frames - written, avail)
            out[written : written + chunk] = cur_buf[self._current_pos : self._current_pos + chunk]
            written += chunk
            self._current_pos = (self._current_pos + chunk) % cur_len

        # 2. Si no hay modulación, aplicar volumen y retornar
        if not self._is_modulating or not self.target_key:
            return out * self.volume

        # 3. Si hay modulación activa, mezclar con el tono objetivo aplicando curvas de crossfade
        tar_buf = self.generate_pad_loop(self.target_key)
        tar_len = len(tar_buf)
        tar_out = np.zeros((frames, 2), dtype=np.float32)

        written_tar = 0
        while written_tar < frames:
            avail_tar = tar_len - self._target_pos
            chunk_tar = min(frames - written_tar, avail_tar)
            tar_out[written_tar : written_tar + chunk_tar] = tar_buf[self._target_pos : self._target_pos + chunk_tar]
            written_tar += chunk_tar
            self._target_pos = (self._target_pos + chunk_tar) % tar_len

        # Calcular curva de fundido cruzado isopotente (equal-power)
        f_len = float(self._crossfade_len)
        step_indices = self._crossfade_pos + np.arange(frames, dtype=np.float32)
        norm_t = np.clip(step_indices / f_len, 0.0, 1.0)[:, np.newaxis]

        # f_out = cos(t * pi/2), f_in = sin(t * pi/2)
        f_out = np.cos(norm_t * (np.pi * 0.5))
        f_in = np.sin(norm_t * (np.pi * 0.5))

        out = (out * f_out + tar_out * f_in) * self.volume
        self._crossfade_pos += frames

        # Si el fundido terminó, consolidar el nuevo tono
        if self._crossfade_pos >= self._crossfade_len:
            self.current_key = self.target_key
            self.target_key = None
            self._is_modulating = False
            self._current_pos = self._target_pos

        return out.astype(np.float32)

    def get_status(self) -> dict:
        """Devuelve el estado serializable del pad para WebSockets y APIs."""
        return {
            "is_active": self.is_active,
            "current_key": self.current_key,
            "target_key": self.target_key,
            "is_modulating": self._is_modulating,
            "volume": round(self.volume, 2),
            "available_keys": CANONICAL_KEYS,
        }
