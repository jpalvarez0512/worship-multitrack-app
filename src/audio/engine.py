"""
Motor Central de Reproducción y Mezcla Multitrack en Tiempo Real
Subagente responsable: 02-audio-multitrack-engineer
"""

import threading
import time
from enum import Enum
from typing import Callable, Dict, List, Optional
import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None

from src.audio.stem import StemTrack


class RoutingMode(str, Enum):
    """
    Modos de ruteo de salida de audio para la iglesia.
    """
    # Modo Split: Canal Izquierdo (In-Ears / Click / Guía), Canal Derecho (Sala / FOH mono)
    SPLIT_STEREO = "split_stereo"
    # Modo Estéreo Normal: Mezcla completa en estéreo para ensayos o interfaces multicanal
    NORMAL_STEREO = "normal_stereo"


class MultitrackEngine:
    """
    Motor multipista en tiempo real optimizado para culto en vivo.
    Maneja múltiples stems sincronizados, ruteo diferenciado (FOH vs Monitores)
    y provee el reloj maestro de tiempo para la sincronización de acordes y letras.
    """

    def __init__(
        self,
        sample_rate: int = 44100,
        buffer_size: int = 256,
        routing_mode: RoutingMode = RoutingMode.SPLIT_STEREO,
        output_device: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.routing_mode = routing_mode
        self.output_device = output_device

        # Control de estado y transporte
        self._is_playing = False
        self._current_frame = 0
        self._master_volume = 1.0
        self._cue_volume = 1.0  # Ganancia para monitores/auriculares (Click + Guía)

        # Contenedor de stems y sincronización de hilos
        self._stems: Dict[str, StemTrack] = {}
        self._lock = threading.RLock()
        self._stream: Optional[object] = None

        # Suscriptores del reloj de tiempo (servidor WebSocket / pantallas)
        self._tick_callbacks: List[Callable[[float, bool], None]] = []
        self._ticker_thread: Optional[threading.Thread] = None
        self._stop_ticker_event = threading.Event()

    # --------------------------------------------------------------------------
    # Gestión de Stems
    # --------------------------------------------------------------------------

    def add_stem(self, stem: StemTrack) -> None:
        """Agrega o reemplaza un stem en el motor de mezcla."""
        with self._lock:
            self._stems[stem.name] = stem

    def remove_stem(self, name: str) -> None:
        """Elimina un stem de la mezcla."""
        with self._lock:
            self._stems.pop(name, None)

    def get_stem(self, name: str) -> Optional[StemTrack]:
        """Obtiene una pista por su nombre."""
        with self._lock:
            return self._stems.get(name)

    def list_stems(self) -> List[StemTrack]:
        """Devuelve la lista actual de stems."""
        with self._lock:
            return list(self._stems.values())

    def clear_stems(self) -> None:
        """Limpia todos los stems del motor."""
        was_playing = self.is_playing
        if was_playing:
            self.stop()
        with self._lock:
            self._stems.clear()
            self._current_frame = 0

    # --------------------------------------------------------------------------
    # Controles de Transporte y Reloj Maestro
    # --------------------------------------------------------------------------

    def play(self) -> None:
        """Inicia la reproducción sincronizada de todos los stems."""
        if sd is None:
            raise RuntimeError("sounddevice no está instalado. Instálalo con pip install sounddevice.")

        with self._lock:
            if self._is_playing:
                return
            if not self._stems:
                return

        self._ensure_stream_open()

        with self._lock:
            self._is_playing = True

        self._start_ticker()

    def pause(self) -> None:
        """Pausa la reproducción manteniendo la posición actual."""
        with self._lock:
            self._is_playing = False
        self._stop_ticker()

    def stop(self) -> None:
        """Detiene la reproducción y rebobina al inicio."""
        stream_ref = None
        with self._lock:
            self._is_playing = False
            self._current_frame = 0
            stream_ref = self._stream

        if stream_ref is not None:
            try:
                stream_ref.stop()
            except Exception:
                pass

        self._stop_ticker()
        self._notify_tick()

    def seek(self, position_seconds: float) -> None:
        """Salta a un punto específico de la canción en segundos."""
        with self._lock:
            target_frame = int(max(0.0, position_seconds) * self.sample_rate)
            self._current_frame = target_frame
        self._notify_tick()

    @property
    def is_playing(self) -> bool:
        """Indica si el motor está actualmente reproduciendo."""
        return self._is_playing

    @property
    def current_position_seconds(self) -> float:
        """Posición actual del reloj maestro en segundos con precisión de muestra."""
        with self._lock:
            return self._current_frame / float(self.sample_rate)

    @property
    def duration_seconds(self) -> float:
        """Duración total de la canción (determinada por el stem más largo)."""
        with self._lock:
            if not self._stems:
                return 0.0
            return max(stem.duration_seconds for stem in self._stems.values())

    @property
    def total_frames(self) -> int:
        """Cantidad máxima de frames entre todos los stems."""
        with self._lock:
            if not self._stems:
                return 0
            return max(stem.total_frames for stem in self._stems.values())

    def set_master_volume(self, volume: float) -> None:
        """Ajusta el volumen general del canal de sala (0.0 a 1.5)."""
        with self._lock:
            self._master_volume = max(0.0, min(1.5, float(volume)))

    def set_cue_volume(self, volume: float) -> None:
        """Ajusta el volumen general del canal de auriculares (0.0 a 1.5)."""
        with self._lock:
            self._cue_volume = max(0.0, min(1.5, float(volume)))

    def set_routing_mode(self, mode: RoutingMode) -> None:
        """Cambia entre modo Split (L=Cue, R=Sala) y Estéreo Normal."""
        with self._lock:
            self.routing_mode = mode

    # --------------------------------------------------------------------------
    # Callback de Audio en Tiempo Real (Sounddevice)
    # --------------------------------------------------------------------------

    def _ensure_stream_open(self) -> None:
        """Inicializa el flujo de salida de sounddevice si no está activo."""
        if self._stream is None or not self._stream.active:
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                blocksize=self.buffer_size,
                device=self.output_device,
                channels=2,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()

    def _audio_callback(self, outdata: np.ndarray, frames: int, time_info, status) -> None:
        """
        Callback de tiempo real invocado por el hardware de audio.
        Mezcla los stems activos según su volumen, mute, solo y asignación de ruteo.
        """
        outdata.fill(0.0)

        if not self._is_playing:
            return

        with self._lock:
            curr = self._current_frame
            max_frames = self.total_frames

            # Si llegamos al final de la canción
            if curr >= max_frames:
                self._is_playing = False
                return

            # Detectar si hay algún stem en modo SOLO
            has_solo = any(stem.solo for stem in self._stems.values())

            # Buffers independientes para mezcla de Sala (Master) y Auriculares (Cue)
            master_mix = np.zeros((frames, 2), dtype=np.float32)
            cue_mix = np.zeros((frames, 2), dtype=np.float32)

            for stem in self._stems.values():
                if has_solo and not stem.solo:
                    continue
                if stem.mute:
                    continue

                chunk = stem.get_slice(curr, frames)
                route = stem.route

                if route in ("master", "both"):
                    master_mix += chunk
                if route in ("cue", "both"):
                    cue_mix += chunk

            # Aplicación de modo de ruteo
            if self.routing_mode == RoutingMode.SPLIT_STEREO:
                # Canal 0 (Izquierdo / L) = Monitores In-Ears (Click + Guía + banda)
                cue_mono = (cue_mix[:, 0] + cue_mix[:, 1]) * 0.5 * self._cue_volume
                # Canal 1 (Derecho / R) = Consola FOH (Solo instrumentos, JAMÁS click ni guía)
                master_mono = (master_mix[:, 0] + master_mix[:, 1]) * 0.5 * self._master_volume

                outdata[:, 0] = np.clip(cue_mono, -1.0, 1.0)
                outdata[:, 1] = np.clip(master_mono, -1.0, 1.0)
            else:
                # Modo Estéreo Normal: Mezcla completa en ambos canales
                full_mix = (master_mix * self._master_volume) + (cue_mix * self._cue_volume)
                outdata[:, 0] = np.clip(full_mix[:, 0], -1.0, 1.0)
                outdata[:, 1] = np.clip(full_mix[:, 1], -1.0, 1.0)

            self._current_frame += frames

    # --------------------------------------------------------------------------
    # Hilo Ticker de Sincronización para Red y Pantallas
    # --------------------------------------------------------------------------

    def register_tick_listener(self, callback: Callable[[float, bool], None]) -> None:
        """Registra un callback para recibir actualizaciones de posición temporal."""
        if callback not in self._tick_callbacks:
            self._tick_callbacks.append(callback)

    def _start_ticker(self) -> None:
        """Inicia el temporizador de emisión de posición."""
        self._stop_ticker_event.clear()
        if self._ticker_thread is None or not self._ticker_thread.is_alive():
            self._ticker_thread = threading.Thread(target=self._ticker_loop, daemon=True)
            self._ticker_thread.start()

    def _stop_ticker(self) -> None:
        """Detiene el hilo ticker."""
        self._stop_ticker_event.set()

    def _ticker_loop(self) -> None:
        """Bucle periódico a 25 Hz (cada 40 ms) para notificar la posición actual."""
        while not self._stop_ticker_event.is_set() and self._is_playing:
            self._notify_tick()
            time.sleep(0.04)

    def _notify_tick(self) -> None:
        """Emite el evento con la posición actual a todos los suscriptores."""
        pos = self.current_position_seconds
        playing = self._is_playing
        for cb in self._tick_callbacks:
            try:
                cb(pos, playing)
            except Exception:
                pass

    def close(self) -> None:
        """Cierra el motor de audio y libera el hardware de sonido."""
        self.stop()
        stream_to_close = None
        with self._lock:
            stream_to_close = self._stream
            self._stream = None

        if stream_to_close is not None:
            try:
                stream_to_close.close()
            except Exception:
                pass
