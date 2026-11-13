"""
Módulo de Gestión de Stems y Pistas de Audio Individuales
Subagente responsable: 02-audio-multitrack-engineer
"""

import os
import wave
from typing import Dict, Optional, Tuple
import numpy as np
from src.audio.pitch_shifter import GLOBAL_PITCH_SHIFTER


class StemTrack:
    """
    Representa una pista individual (stem) dentro de un multitrack de adoración.
    Ejemplos: Batería, Bajo, Guitarras, Click (Metrónomo), Guía (Cues hablados).
    """

    def __init__(
        self,
        name: str,
        audio_data: Optional[np.ndarray] = None,
        sample_rate: int = 44100,
        route: Optional[str] = None,
        volume: float = 1.0,
        pan: float = 0.0,
        mute: bool = False,
        solo: bool = False,
        file_path: Optional[str] = None,
    ):
        self.name = name
        self.sample_rate = sample_rate
        self.volume = max(0.0, float(volume))
        self.pan = max(-1.0, min(1.0, float(pan)))
        self.mute = bool(mute)
        self.solo = bool(solo)
        self.file_path = file_path

        # Ruteo por defecto según la naturaleza del stem:
        # 'cue': Solo va a los auriculares de los músicos (Click y Guía).
        # 'master': Va a la sala principal (FOH).
        # 'both': Va a ambos canales.
        if route is not None:
            self.route = route
        else:
            lower_name = name.lower()
            if any(cue_word in lower_name for cue_word in [
                "click", "clic", "metronomo", "metrónomo", "guia", "guía", "guide", "cue", "count",
            ]):
                self.route = "cue"
            else:
                self.route = "master"

        # Matriz de audio normalizada en float32 con forma (N, 2)
        if audio_data is not None:
            self.raw_audio_data = self._ensure_stereo_float32(audio_data)
        else:
            self.raw_audio_data = np.zeros((0, 2), dtype=np.float32)

        self.audio_data = self.raw_audio_data
        self.current_transpose: int = 0
        self._transpose_cache: Dict[int, np.ndarray] = {0: self.raw_audio_data}

    def is_cue_track(self) -> bool:
        """Determina si la pista es de referencia rítmica o vocal (Click o Guía)."""
        lower = self.name.lower()
        return any(
            cue_word in lower
            for cue_word in ("click", "clic", "metronomo", "metrónomo", "guia", "guía", "guide", "cue", "count")
        )

    def transpose(self, semitones: int) -> None:
        """
        Transpone la pista en +/- semitonos manteniendo la velocidad idéntica.
        Las pistas de Click y Guía se omiten intencionalmente para conservar su timbre natural.
        """
        if self.is_cue_track() or semitones == self.current_transpose:
            return

        if semitones == 0:
            self.audio_data = self.raw_audio_data
            self.current_transpose = 0
            return

        if semitones in self._transpose_cache:
            self.audio_data = self._transpose_cache[semitones]
            self.current_transpose = semitones
            return

        shifted = GLOBAL_PITCH_SHIFTER.shift_pitch(self.raw_audio_data, semitones, self.sample_rate)
        self._transpose_cache[semitones] = shifted
        self.audio_data = shifted
        self.current_transpose = semitones

    @classmethod
    def load_from_file(
        cls,
        file_path: str,
        name: Optional[str] = None,
        target_sample_rate: int = 44100,
        route: Optional[str] = None,
    ) -> "StemTrack":
        """
        Carga una pista de audio desde un archivo WAV, FLAC, MP3 u OGG.
        Usa la librería estándar `wave` para WAV sin dependencias externas,
        y `soundfile` / `miniaudio` si están disponibles para formatos comprimidos.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Archivo de audio no encontrado: {file_path}")

        stem_name = name or os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1].lower()

        data: np.ndarray
        sr: int

        # 1. Intento nativo con módulo wave (sin librerías externas) para archivos WAV
        if ext == ".wav":
            try:
                data, sr = cls._read_wav_builtin(file_path)
            except Exception:
                # Si wave falla por compresión o formato extendido, intentar con soundfile
                data, sr = cls._read_external(file_path)
        else:
            # Para MP3, FLAC, OGG requerimos decodificador externo
            data, sr = cls._read_external(file_path)

        # Conversión básica de sample rate si difiere
        if sr != target_sample_rate and len(data) > 0:
            data = cls._resample_simple(data, sr, target_sample_rate)
            sr = target_sample_rate

        return cls(
            name=stem_name,
            audio_data=data,
            sample_rate=sr,
            route=route,
            file_path=file_path,
        )

    @staticmethod
    def _read_wav_builtin(file_path: str) -> Tuple[np.ndarray, int]:
        """Lee un archivo WAV usando el módulo estándar `wave` de Python."""
        with wave.open(file_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

            # Conversión según ancho de muestra a float32 (-1.0 a 1.0)
            if sampwidth == 2:  # 16-bit PCM
                int_data = np.frombuffer(raw_bytes, dtype=np.int16)
                float_data = int_data.astype(np.float32) / 32768.0
            elif sampwidth == 3:  # 24-bit PCM
                # Conversión de 24 bits
                raw_bytes_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
                int_data = np.zeros(n_frames * n_channels, dtype=np.int32)
                int_data = (
                    raw_bytes_arr[0::3].astype(np.int32)
                    | (raw_bytes_arr[1::3].astype(np.int32) << 8)
                    | (raw_bytes_arr[2::3].astype(np.int32) << 16)
                )
                int_data[int_data >= 0x800000] -= 0x1000000
                float_data = int_data.astype(np.float32) / 8388608.0
            elif sampwidth == 4:  # 32-bit PCM entero (los WAV float32 no los abre `wave` y van a soundfile)
                int_data = np.frombuffer(raw_bytes, dtype=np.int32)
                float_data = int_data.astype(np.float32) / 2147483648.0
            else:
                int_data = np.frombuffer(raw_bytes, dtype=np.uint8)
                float_data = (int_data.astype(np.float32) - 128.0) / 128.0

            if n_channels == 1:
                stereo_data = np.column_stack((float_data, float_data))
            else:
                stereo_data = float_data.reshape(-1, n_channels)[:, :2]

            return stereo_data, framerate

    @staticmethod
    def _read_external(file_path: str) -> Tuple[np.ndarray, int]:
        """Intenta decodificar con soundfile o miniaudio."""
        try:
            import soundfile as sf
            data, sr = sf.read(file_path, dtype="float32", always_2d=True)
            if data.shape[1] == 1:
                data = np.column_stack((data[:, 0], data[:, 0]))
            return data[:, :2], sr
        except ImportError:
            pass

        try:
            import miniaudio
            decoded = miniaudio.decode_file(file_path, nchannels=2, sample_rate=44100)
            raw = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
            return raw.reshape(-1, 2), decoded.sample_rate
        except ImportError:
            raise RuntimeError(
                f"Para decodificar {file_path} se requiere 'soundfile' o 'miniaudio'. "
                "Los archivos .wav estándar se soportan nativamente."
            )

    @staticmethod
    def _ensure_stereo_float32(data: np.ndarray) -> np.ndarray:
        """Asegura que el array sea float32 y con dimensiones (N, 2)."""
        arr = np.asarray(data, dtype=np.float32)
        if arr.ndim == 1:
            return np.column_stack((arr, arr))
        elif arr.ndim == 2:
            if arr.shape[1] == 1:
                return np.column_stack((arr[:, 0], arr[:, 0]))
            elif arr.shape[1] >= 2:
                return arr[:, :2]
        raise ValueError(f"Formato de dimensiones no admitido para stem: {arr.shape}")

    @staticmethod
    def _resample_simple(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Interpolación lineal rápida para igualar sample rate."""
        if orig_sr == target_sr:
            return data
        orig_len = len(data)
        target_len = int(orig_len * (target_sr / orig_sr))
        orig_indices = np.linspace(0, orig_len - 1, num=orig_len)
        target_indices = np.linspace(0, orig_len - 1, num=target_len)
        
        left_ch = np.interp(target_indices, orig_indices, data[:, 0]).astype(np.float32)
        right_ch = np.interp(target_indices, orig_indices, data[:, 1]).astype(np.float32)
        return np.column_stack((left_ch, right_ch))

    def add_slice_to(self, out_buffer: np.ndarray, start_frame: int, num_frames: int) -> None:
        """
        Acumula directamente el slice de audio en out_buffer sin crear arrays intermedios en el heap (Zero-Allocation).
        Aplica volumen y paneo con operaciones vectorizadas de alta velocidad.
        """
        total_len = len(self.audio_data)
        if self.mute or start_frame >= total_len or start_frame + num_frames <= 0:
            return

        gain = self.volume
        if gain <= 0.0001:
            return

        src_start = max(0, start_frame)
        src_end = min(total_len, start_frame + num_frames)
        dst_start = max(0, -start_frame)
        dst_end = dst_start + (src_end - src_start)

        chunk = self.audio_data[src_start:src_end]

        if self.pan == 0.0:
            if gain == 1.0:
                out_buffer[dst_start:dst_end, :2] += chunk
            else:
                out_buffer[dst_start:dst_end, 0] += chunk[:, 0] * gain
                out_buffer[dst_start:dst_end, 1] += chunk[:, 1] * gain
        else:
            if self.pan < 0.0:
                gain_l = gain
                gain_r = gain * (1.0 + self.pan)
            else:
                gain_l = gain * (1.0 - self.pan)
                gain_r = gain
            out_buffer[dst_start:dst_end, 0] += chunk[:, 0] * gain_l
            out_buffer[dst_start:dst_end, 1] += chunk[:, 1] * gain_r

    def get_slice(self, start_frame: int, num_frames: int) -> np.ndarray:
        """
        Extrae un bloque de audio de longitud `num_frames` a partir de `start_frame`.
        Si el rango solicitado sobrepasa la duración, rellena con ceros (silencio).
        Aplica volumen y paneo.
        """
        out = np.zeros((num_frames, 2), dtype=np.float32)
        self.add_slice_to(out, start_frame, num_frames)
        return out

    @property
    def duration_seconds(self) -> float:
        """Duración total del stem en segundos."""
        if self.sample_rate <= 0:
            return 0.0
        return len(self.audio_data) / float(self.sample_rate)

    @property
    def total_frames(self) -> int:
        """Cantidad total de muestras de audio (frames)."""
        return len(self.audio_data)
