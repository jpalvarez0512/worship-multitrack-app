"""
Modulo Extractor de Rejilla Ritmica y Deteccion de Compases
Worship Multitrack Live
Analiza la pista de Click (metronomo) para detectar con precision de milisegundos
el BPM real, la ubicacion de cada pulso y los tiempos fuertes (tiempo 1 del compas).
"""

from dataclasses import dataclass, field
import math
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class RhythmicGrid:
    """Rejilla temporal anclada a pulsos y compases musicales."""
    bpm: float
    time_signature: str = "4/4"
    beats_per_bar: int = 4
    beat_duration: float = 0.5  # segundos por pulso
    bar_duration: float = 2.0   # segundos por compas
    duration_seconds: float = 0.0
    beat_times: List[float] = field(default_factory=list)
    bar_times: List[float] = field(default_factory=list)

    def snap_to_nearest_beat(self, time_sec: float, max_tolerance: float = 0.120) -> float:
        """
        Atrae magneticamente un instante al pulso musical mas cercano dentro de una
        ventana de tolerancia (por defecto +/- 120 ms).
        """
        if not self.beat_times:
            return time_sec

        # Busqueda binaria o aproximada en beat_times
        idx = int(np.searchsorted(self.beat_times, time_sec))
        candidates = []
        if idx < len(self.beat_times):
            candidates.append(self.beat_times[idx])
        if idx > 0:
            candidates.append(self.beat_times[idx - 1])

        if not candidates:
            return time_sec

        closest = min(candidates, key=lambda b: abs(b - time_sec))
        if abs(closest - time_sec) <= max_tolerance:
            return round(float(closest), 3)
        return round(time_sec, 3)

    def snap_to_nearest_downbeat(self, time_sec: float, max_tolerance: float = 0.250) -> float:
        """
        Atrae un instante al inicio de compas (pulso 1) mas cercano dentro de la tolerancia.
        """
        if not self.bar_times:
            return self.snap_to_nearest_beat(time_sec, max_tolerance)

        idx = int(np.searchsorted(self.bar_times, time_sec))
        candidates = []
        if idx < len(self.bar_times):
            candidates.append(self.bar_times[idx])
        if idx > 0:
            candidates.append(self.bar_times[idx - 1])

        if not candidates:
            return time_sec

        closest = min(candidates, key=lambda b: abs(b - time_sec))
        if abs(closest - time_sec) <= max_tolerance:
            return round(float(closest), 3)
        return round(time_sec, 3)

    def get_bar_and_beat(self, time_sec: float) -> Tuple[int, int]:
        """
        Determina a que numero de compas (0-indexado) y pulso (1-indexado)
        corresponde un instante temporal dado.
        """
        if time_sec <= 0 or not self.beat_times:
            return (0, 1)

        idx = int(np.searchsorted(self.beat_times, time_sec))
        if idx >= len(self.beat_times):
            idx = len(self.beat_times) - 1

        bar_idx = idx // self.beats_per_bar
        beat_in_bar = (idx % self.beats_per_bar) + 1
        return (bar_idx, beat_in_bar)

    def to_dict(self) -> dict:
        return {
            "bpm": round(self.bpm, 2),
            "time_signature": self.time_signature,
            "beats_per_bar": self.beats_per_bar,
            "beat_duration": round(self.beat_duration, 4),
            "bar_duration": round(self.bar_duration, 4),
            "duration_seconds": round(self.duration_seconds, 2),
            "total_beats": len(self.beat_times),
            "total_bars": len(self.bar_times),
        }


def extract_rhythmic_grid_from_audio(
    click_audio: np.ndarray,
    sample_rate: int = 44100,
    declared_bpm: Optional[float] = None,
    time_signature: str = "4/4",
    total_duration: Optional[float] = None,
) -> RhythmicGrid:
    """
    Analiza una matriz de audio del stem de Click (metronomo) para detectar transitorios,
    calcular el tempo real exacto y construir la rejilla de pulsos y compases.
    """
    beats_per_bar = 4
    if "/" in time_signature:
        try:
            beats_per_bar = int(time_signature.split("/")[0])
        except ValueError:
            beats_per_bar = 4

    # Determinar longitud total en segundos
    if click_audio is not None and len(click_audio) > 0:
        duration_sec = len(click_audio) / float(sample_rate)
    else:
        duration_sec = total_duration or 180.0

    # 1. Si no hay audio de click disponible, construir rejilla teorica
    if click_audio is None or len(click_audio) < sample_rate:
        return build_synthetic_grid(
            bpm=declared_bpm or 72.0,
            time_signature=time_signature,
            duration_seconds=duration_sec,
        )

    # 2. Convertir audio a mono absoluto
    if click_audio.ndim > 1:
        mono = np.max(np.abs(click_audio), axis=1)
    else:
        mono = np.abs(click_audio)

    peak_max = float(np.max(mono))
    if peak_max < 0.01:
        # Pista en silencio, usar BPM declarado
        return build_synthetic_grid(
            bpm=declared_bpm or 72.0,
            time_signature=time_signature,
            duration_seconds=duration_sec,
        )

    # 3. Deteccion de picos de transitorios (Click Onsets)
    # Tamano de ventana para suavizado de envolvente (~5 ms)
    win_size = int(0.005 * sample_rate)
    envelope = np.convolve(mono, np.ones(win_size) / win_size, mode="same")

    threshold = 0.25 * peak_max
    # Distancia minima entre clics: 180 ms (~330 BPM maximo)
    min_dist = int(0.180 * sample_rate)

    detected_peaks = []
    i = 0
    total_len = len(envelope)
    while i < total_len:
        if envelope[i] > threshold:
            # Buscar el pico local en una ventana de 25 ms
            window_end = min(i + int(0.025 * sample_rate), total_len)
            local_max_idx = i + int(np.argmax(envelope[i:window_end]))
            peak_time = local_max_idx / float(sample_rate)
            detected_peaks.append((peak_time, envelope[local_max_idx]))
            i = local_max_idx + min_dist
        else:
            i += win_size

    # Si se detectaron menos de 4 clics, usar rejilla teorica
    if len(detected_peaks) < 4:
        return build_synthetic_grid(
            bpm=declared_bpm or 72.0,
            time_signature=time_signature,
            duration_seconds=duration_sec,
        )

    peak_times = [p[0] for p in detected_peaks]
    intervals = np.diff(peak_times)

    # Filtrar intervalos validos entre 0.20s y 2.0s (30 a 300 BPM)
    valid_intervals = [float(dt) for dt in intervals if 0.20 <= dt <= 2.0]
    if not valid_intervals:
        return build_synthetic_grid(
            bpm=declared_bpm or 72.0,
            time_signature=time_signature,
            duration_seconds=duration_sec,
        )

    median_interval = float(np.median(valid_intervals))
    calculated_bpm = 60.0 / median_interval

    # Si se proporciono un BPM declarado, verificar si esta cercano
    final_bpm = calculated_bpm
    if declared_bpm and abs(calculated_bpm - declared_bpm) < 4.0:
        final_bpm = float(declared_bpm)

    beat_dur = 60.0 / final_bpm
    bar_dur = beat_dur * beats_per_bar

    # Determinar primer pulso (t0) anclado al primer clic fuerte detectado
    first_peak = peak_times[0]
    # Retroceder hasta t=0 en multiplos de beat_dur
    t0 = first_peak % beat_dur

    beat_times_list = []
    t = t0
    while t < duration_sec:
        beat_times_list.append(round(t, 4))
        t += beat_dur

    bar_times_list = []
    t_bar = t0
    while t_bar < duration_sec:
        bar_times_list.append(round(t_bar, 4))
        t_bar += bar_dur

    return RhythmicGrid(
        bpm=round(final_bpm, 2),
        time_signature=time_signature,
        beats_per_bar=beats_per_bar,
        beat_duration=round(beat_dur, 4),
        bar_duration=round(bar_dur, 4),
        duration_seconds=round(duration_sec, 2),
        beat_times=beat_times_list,
        bar_times=bar_times_list,
    )


def build_synthetic_grid(
    bpm: float,
    time_signature: str = "4/4",
    duration_seconds: float = 180.0,
) -> RhythmicGrid:
    """Construye una rejilla ritmica regular matematica a partir de BPM y compas."""
    effective_bpm = max(30.0, float(bpm))
    beats_per_bar = 4
    if "/" in time_signature:
        try:
            beats_per_bar = int(time_signature.split("/")[0])
        except ValueError:
            beats_per_bar = 4

    beat_dur = 60.0 / effective_bpm
    bar_dur = beat_dur * beats_per_bar

    beat_times = []
    t = 0.0
    while t < duration_seconds:
        beat_times.append(round(t, 4))
        t += beat_dur

    bar_times = []
    t_bar = 0.0
    while t_bar < duration_seconds:
        bar_times.append(round(t_bar, 4))
        t_bar += bar_dur

    return RhythmicGrid(
        bpm=round(effective_bpm, 2),
        time_signature=time_signature,
        beats_per_bar=beats_per_bar,
        beat_duration=round(beat_dur, 4),
        bar_duration=round(bar_dur, 4),
        duration_seconds=round(duration_seconds, 2),
        beat_times=beat_times,
        bar_times=bar_times,
    )
