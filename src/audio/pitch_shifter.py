"""
Módulo de Transposición y Cambio de Tono en Tiempo Real (Pitch Shifting)
Worship Multitrack Live
Permite transponer pistas de audio WAV/MP3 (+/- 4 semitonos) preservando
exactamente el tempo y la duración de la canción mediante Phase Vocoder con NumPy.
"""

from typing import Dict, Tuple
import numpy as np


class PitchShifter:
    """Procesador de cambio de tono y caché en memoria para stems multitrack."""

    def __init__(self, n_fft: int = 2048, hop_length: int = 512):
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.window = np.hanning(n_fft).astype(np.float32)

    def shift_pitch(self, audio: np.ndarray, semitones: int, sample_rate: int = 44100) -> np.ndarray:
        """
        Cambia el tono del arreglo de audio (N, 2) en 'semitones' (-7 a +7)
        sin alterar la velocidad ni la longitud temporal.
        """
        if semitones == 0 or len(audio) == 0:
            return audio

        ratio = 2.0 ** (float(semitones) / 12.0)
        orig_len = len(audio)
        n_fft = self.n_fft
        hop = self.hop_length
        window = self.window
        rate = ratio

        out_channels = []
        for ch in range(audio.shape[1]):
            sig = np.ascontiguousarray(audio[:, ch], dtype=np.float32)
            n_frames = int(np.floor((len(sig) - n_fft) / hop)) + 1
            if n_frames <= 2:
                out_channels.append(sig)
                continue

            # Ventaneo y STFT
            frames = np.lib.stride_tricks.as_strided(
                sig,
                shape=(n_frames, n_fft),
                strides=(sig.strides[0] * hop, sig.strides[0]),
            )
            stft = np.fft.rfft(frames * window, axis=1)

            # Avance de fase del Phase Vocoder
            phase_adv = 2.0 * np.pi * hop * np.arange(stft.shape[1], dtype=np.float32) / float(n_fft)
            t_out = np.arange(0, n_frames - 1, rate, dtype=np.float32)
            out_frames = len(t_out)
            synth_spec = np.zeros((out_frames, stft.shape[1]), dtype=np.complex64)

            phase = np.angle(stft[0]).astype(np.float32)
            synth_spec[0] = stft[0]

            # Re-síntesis de fase
            for i, t in enumerate(t_out[1:], 1):
                t_floor = int(np.floor(t))
                frac = float(t - t_floor)
                t_next = min(t_floor + 1, n_frames - 1)
                mag = (1.0 - frac) * np.abs(stft[t_floor]) + frac * np.abs(stft[t_next])
                dphase = np.angle(stft[t_next]) - np.angle(stft[t_floor]) - phase_adv
                dphase = (dphase + np.pi) % (2.0 * np.pi) - np.pi
                phase += phase_adv + dphase
                synth_spec[i] = mag * (np.cos(phase) + 1j * np.sin(phase))

            # iSTFT y reconstrucción por solapamiento y suma (Overlap-Add)
            inv_frames = (np.fft.irfft(synth_spec, axis=1) * window).astype(np.float32)
            synth_len = (out_frames - 1) * hop + n_fft
            out_sig = np.zeros(synth_len, dtype=np.float32)
            win_sum = np.zeros(synth_len, dtype=np.float32)

            for i in range(out_frames):
                pos = i * hop
                out_sig[pos : pos + n_fft] += inv_frames[i]
                win_sum[pos : pos + n_fft] += window ** 2

            win_sum[win_sum < 1e-4] = 1.0
            stretched = out_sig / win_sum

            # Remuestreo de vuelta a la longitud original exacta
            stretched_len = len(stretched)
            orig_indices = np.linspace(0, stretched_len - 1, stretched_len, dtype=np.float32)
            target_indices = np.linspace(0, stretched_len - 1, orig_len, dtype=np.float32)
            resampled_ch = np.interp(target_indices, orig_indices, stretched).astype(np.float32)
            out_channels.append(resampled_ch)

        return np.column_stack((out_channels[0], out_channels[1])).astype(np.float32)


# Instancia singleton para reutilizar buffers de FFT y ventanas
GLOBAL_PITCH_SHIFTER = PitchShifter()
