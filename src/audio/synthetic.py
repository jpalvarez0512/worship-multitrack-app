"""
Generador de Pistas Sintéticas de Prueba para Worship Multitrack App
Permite probar el motor de audio y la división de canales sin necesidad de archivos WAV externos.
Subagente responsable: 02-audio-multitrack-engineer
"""

import numpy as np
from src.audio.stem import StemTrack


def generate_click_track(bpm: int = 76, duration_seconds: float = 20.0, sample_rate: int = 44100) -> StemTrack:
    """
    Genera una pista de Metrónomo / Click sintética precisa.
    Primer tiempo de cada compás en tono alto (1500 Hz), tiempos 2, 3 y 4 en tono medio (800 Hz).
    """
    total_samples = int(duration_seconds * sample_rate)
    click_audio = np.zeros(total_samples, dtype=np.float32)

    beat_interval_samples = int((60.0 / bpm) * sample_rate)
    pulse_length = int(0.025 * sample_rate)  # 25 ms de duración por golpe
    t_pulse = np.linspace(0, 0.025, pulse_length, endpoint=False)

    # Onda de acento (1500 Hz con caída exponencial)
    accent_pulse = np.sin(2 * np.pi * 1500 * t_pulse) * np.exp(-t_pulse * 120)
    # Onda regular (800 Hz con caída exponencial)
    normal_pulse = np.sin(2 * np.pi * 800 * t_pulse) * np.exp(-t_pulse * 120)

    beat_count = 0
    pos = 0
    while pos + pulse_length < total_samples:
        is_accent = (beat_count % 4 == 0)
        pulse = accent_pulse if is_accent else normal_pulse
        click_audio[pos : pos + pulse_length] += pulse * 0.8
        pos += beat_interval_samples
        beat_count += 1

    stereo = np.column_stack((click_audio, click_audio))
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

    beat_interval_samples = int((60.0 / bpm) * sample_rate)
    # Simular un cue al inicio (segundo 0 a 2) y en el compás 4 (segundo 12 aprox)
    t = np.linspace(0, 0.1, int(0.1 * sample_rate), endpoint=False)
    cue_beep = np.sin(2 * np.pi * 1200 * t) * 0.6

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
    Genera una pista instrumental sintética suave (Pad / Bajo) ruteada a 'master' (FOH).
    """
    total_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, total_samples, endpoint=False)
    
    # Onda armónica suave para simular un colchón (pad)
    waveform = (
        0.5 * np.sin(2 * np.pi * frequency * t)
        + 0.3 * np.sin(2 * np.pi * (frequency * 1.5) * t)
        + 0.2 * np.sin(2 * np.pi * (frequency * 2.0) * t)
    ) * 0.4

    stereo = np.column_stack((waveform, waveform))
    return StemTrack(
        name=name,
        audio_data=stereo,
        sample_rate=sample_rate,
        route="master",
        volume=0.7,
    )
