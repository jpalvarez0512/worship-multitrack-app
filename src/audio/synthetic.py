"""
Generador de Pistas Sintéticas de Prueba para Worship Multitrack App
Permite probar el motor de audio y la división de canales sin necesidad de archivos WAV externos.
Generación ultra-rápida vectorizada con repetición en memoria C (tiling).
Subagente responsable: 02-audio-multitrack-engineer
"""

import numpy as np
from src.audio.stem import StemTrack


def generate_click_track(bpm: int = 76, duration_seconds: float = 20.0, sample_rate: int = 44100) -> StemTrack:
    """
    Genera una pista de Metrónomo / Click sintética precisa a máxima velocidad con tiling.
    Primer tiempo de cada compás en tono alto (1500 Hz), tiempos 2, 3 y 4 en tono medio (800 Hz).
    """
    total_samples = int(duration_seconds * sample_rate)
    beat_interval_samples = max(int((60.0 / bpm) * sample_rate), 1)
    measure_samples = beat_interval_samples * 4
    one_measure = np.zeros(measure_samples, dtype=np.float32)

    pulse_length = min(int(0.025 * sample_rate), beat_interval_samples)  # 25 ms de duración por golpe
    t_pulse = np.linspace(0, 0.025, pulse_length, endpoint=False, dtype=np.float32)

    # Onda de acento (1500 Hz con caída exponencial)
    accent_pulse = (np.sin(2 * np.pi * 1500 * t_pulse) * np.exp(-t_pulse * 120)).astype(np.float32)
    # Onda regular (800 Hz con caída exponencial)
    normal_pulse = (np.sin(2 * np.pi * 800 * t_pulse) * np.exp(-t_pulse * 120)).astype(np.float32)

    # Beat 1 (Acento)
    one_measure[0:pulse_length] += accent_pulse * 0.8
    # Beats 2, 3, 4 (Normal)
    for b in range(1, 4):
        pos = b * beat_interval_samples
        if pos + pulse_length <= measure_samples:
            one_measure[pos : pos + pulse_length] += normal_pulse * 0.8

    num_measures = int(np.ceil(total_samples / measure_samples))
    tiled = np.tile(one_measure, num_measures)[:total_samples]
    stereo = np.column_stack((tiled, tiled))

    return StemTrack(
        name="Click",
        audio_data=stereo,
        sample_rate=sample_rate,
        route="cue",
        volume=0.8,
    )


def generate_guide_cues(bpm: int = 76, duration_seconds: float = 20.0, sample_rate: int = 44100) -> StemTrack:
    """
    Genera una pista de Guía sintética simulada con pulsos de advertencia antes de cada sección.
    Ruteada automáticamente al canal 'cue' (auriculares de músicos).
    """
    total_samples = int(duration_seconds * sample_rate)
    guide_audio = np.zeros(total_samples, dtype=np.float32)

    # Simular un cue al inicio (segundo 0 a 2) y en el compás 4 (segundo 12 aprox)
    t = np.linspace(0, 0.1, int(0.1 * sample_rate), endpoint=False, dtype=np.float32)
    cue_beep = (np.sin(2 * np.pi * 1200 * t) * 0.6).astype(np.float32)

    for cue_time in [0.5, 6.3, 12.6]:
        idx = int(cue_time * sample_rate)
        if idx + len(cue_beep) < total_samples:
            guide_audio[idx : idx + len(cue_beep)] += cue_beep

    stereo = np.column_stack((guide_audio, guide_audio))
    return StemTrack(
        name="Guia",
        audio_data=stereo,
        sample_rate=sample_rate,
        route="cue",
        volume=0.9,
    )


def generate_instrument_stem(
    name: str,
    frequency: float = 220.0,
    duration_seconds: float = 20.0,
    sample_rate: int = 44100,
) -> StemTrack:
    """
    Genera una pista instrumental sintética suave (Pad / Bajo) ruteada a 'master' (FOH)
    a ultra-alta velocidad mediante memoria C repetida (tiling).
    """
    total_samples = int(duration_seconds * sample_rate)
    
    # Generar 1 segundo base del colchón armónico
    t_1s = np.linspace(0, 1.0, sample_rate, endpoint=False, dtype=np.float32)
    waveform_1s = (
        0.5 * np.sin(2 * np.pi * frequency * t_1s)
        + 0.3 * np.sin(2 * np.pi * (frequency * 1.5) * t_1s)
        + 0.2 * np.sin(2 * np.pi * (frequency * 2.0) * t_1s)
    ).astype(np.float32) * 0.4

    num_seconds = max(int(np.ceil(duration_seconds)), 1)
    tiled_waveform = np.tile(waveform_1s, num_seconds)[:total_samples]
    stereo = np.column_stack((tiled_waveform, tiled_waveform))

    return StemTrack(
        name=name,
        audio_data=stereo,
        sample_rate=sample_rate,
        route="master",
        volume=0.7,
    )
