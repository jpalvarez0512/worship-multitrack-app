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

from src.audio.cue_manager import CueManager
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
        buffer_size: int = 1024,
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

        # Buffers preasignados de mezcla en memoria contigua (Zero-Allocation en el callback de audio)
        self._master_mix_buf = np.zeros((self.buffer_size, 2), dtype=np.float32)
        self._cue_mix_buf = np.zeros((self.buffer_size, 2), dtype=np.float32)

        # Suscriptores del reloj de tiempo (servidor WebSocket / pantallas)
        self._tick_callbacks: List[Callable[[float, bool], None]] = []
        self._track_finished_callbacks: List[Callable[[], None]] = []
        self._ticker_thread: Optional[threading.Thread] = None
        self._stop_ticker_event = threading.Event()

        # Métricas de tiempo y compás para saltos musicales cuantizados
        self._bpm: float = 120.0
        self._beats_per_bar: int = 4
        self._pending_jump_frame: Optional[int] = None
        self._pending_jump_label: str = ""
        self._jump_lead_bar_frame: Optional[int] = None
        self._jump_target_bar_frame: Optional[int] = None

        # Modo Bucle Espontáneo de Sección
        self._loop_enabled: bool = False
        self._loop_start_frame: int = 0
        self._loop_end_frame: int = 0
        self._loop_label: str = ""
        self._fade_len: int = 512  # ~11.6 ms a 44.1 kHz (Micro-Crossfade Isopotente)

        # Generador de Guías de Audio Dinámicas (In-Ear Cues en Español)
        self._cue_manager = CueManager(sample_rate=self.sample_rate)
        self._dynamic_cues_enabled: bool = True
        self._active_overlay_cue: Optional[np.ndarray] = None
        self._active_overlay_pos: int = 0
        self._loop_cue_last_fired_frame: int = -1

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
            self._pending_jump_frame = None
            self._pending_jump_label = ""
            self._loop_enabled = False
            self._loop_label = ""
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
            self._pending_jump_frame = None
            self._pending_jump_label = ""
            self._jump_lead_bar_frame = None
            self._jump_target_bar_frame = None
            self._active_overlay_cue = None
            self._active_overlay_pos = 0
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
    # Sincronización Musical, Saltos Cuantizados y Modo Bucle Espontáneo
    # --------------------------------------------------------------------------

    def set_song_timing(self, bpm: float, time_signature: str = "4/4") -> None:
        """Configura el tempo y la métrica de compás para cuantización musical."""
        with self._lock:
            self._bpm = max(30.0, min(float(bpm or 120.0), 300.0))
            beats = 4
            if time_signature and "/" in time_signature:
                try:
                    beats = int(time_signature.split("/")[0])
                except Exception:
                    beats = 4
            self._beats_per_bar = max(1, min(beats, 16))

    @property
    def bar_duration_seconds(self) -> float:
        """Duración en segundos de un compás completo según BPM y métrica."""
        with self._lock:
            return (60.0 / max(10.0, self._bpm)) * self._beats_per_bar

    def schedule_jump(
        self,
        target_seconds: float,
        label: str = "",
        quantize_to_bar: bool = True,
        transition_at_seconds: Optional[float] = None,
    ) -> None:
        """
        Programa un salto cuantizado a una sección musical (ej. Coro, Puente).
        Si se especifica transition_at_seconds (final de la sección original),
        el motor continuará reproduciendo la sección original hasta completarla,
        disparando el compás de aviso con conteo rítmico ("[Sección] ... 2 ... 3 ... 4")
        en el último compás de dicha sección, y ejecutando la transición exactamente
        al inicio de la nueva sección seleccionada.
        """
        target_f = int(max(0.0, target_seconds) * self.sample_rate)
        with self._lock:
            if not self._is_playing or not quantize_to_bar:
                self._current_frame = target_f
                self._pending_jump_frame = None
                self._pending_jump_label = ""
                self._jump_lead_bar_frame = None
                self._jump_target_bar_frame = None
                self._loop_enabled = False
                self._loop_label = ""
            else:
                self._pending_jump_frame = target_f
                self._pending_jump_label = label or "Sección"
                # Desactivar bucle infinito previo si estaba activo para ceder el control al salto
                self._loop_enabled = False
                self._loop_label = ""

                samples_per_beat = max(1, int((60.0 / max(10.0, self._bpm)) * self.sample_rate))
                samples_per_bar = max(1, samples_per_beat * self._beats_per_bar)
                curr = self._current_frame
                next_bar = ((curr // samples_per_bar) + 1) * samples_per_bar

                if transition_at_seconds is not None:
                    target_trans_f = int(max(0.0, transition_at_seconds) * self.sample_rate)
                    # Alinear el final de sección con el compás musical más cercano
                    trans_bar = max(next_bar, round(target_trans_f / samples_per_bar) * samples_per_bar)
                    lead_bar = trans_bar - samples_per_bar

                    # Si el cursor ya está dentro del último compás o muy cerca del final,
                    # otorgamos 1 compás completo a partir de next_bar para asegurar el conteo rítmico
                    if lead_bar <= curr:
                        lead_bar = next_bar
                        trans_bar = next_bar + samples_per_bar

                    self._jump_lead_bar_frame = lead_bar
                    self._jump_target_bar_frame = trans_bar
                else:
                    self._jump_lead_bar_frame = next_bar
                    self._jump_target_bar_frame = next_bar + samples_per_bar
        self._notify_tick()

    def trigger_cue(self, cue_name: str) -> bool:
        """Dispara manualmente una indicación hablada en los in-ears (ej. 'atentos', 'coro', 'corte')."""
        cue_audio = self._cue_manager.get_cue(cue_name)
        if cue_audio is None:
            cue_audio = self._cue_manager.get_cue_for_section(cue_name)
        if cue_audio is not None:
            with self._lock:
                self._active_overlay_cue = cue_audio
                self._active_overlay_pos = 0
            return True
        return False

    @property
    def dynamic_cues_enabled(self) -> bool:
        with self._lock:
            return self._dynamic_cues_enabled

    def set_dynamic_cues_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._dynamic_cues_enabled = bool(enabled)

    def cancel_scheduled_jump(self) -> None:
        """Cancela un salto programado pendiente."""
        with self._lock:
            self._pending_jump_frame = None
            self._pending_jump_label = ""
            self._jump_lead_bar_frame = None
            self._jump_target_bar_frame = None
            self._active_overlay_cue = None
            self._active_overlay_pos = 0
        self._notify_tick()

    def set_section_loop(self, start_seconds: float, end_seconds: float, label: str = "", enabled: bool = True) -> None:
        """Activa o desactiva el bucle infinito sobre una sección específica."""
        with self._lock:
            self._loop_enabled = enabled
            self._loop_start_frame = int(max(0.0, start_seconds) * self.sample_rate)
            self._loop_end_frame = int(max(start_seconds + 0.1, end_seconds) * self.sample_rate)
            self._loop_label = label if enabled else ""
        self._notify_tick()

    def toggle_section_loop(self, start_seconds: float = 0.0, end_seconds: float = 0.0, label: str = "") -> bool:
        """Alterna el estado de bucle para una sección."""
        with self._lock:
            if self._loop_enabled and (not label or self._loop_label == label):
                self._loop_enabled = False
                self._loop_label = ""
            else:
                self._loop_enabled = True
                self._loop_start_frame = int(max(0.0, start_seconds) * self.sample_rate)
                self._loop_end_frame = int(max(start_seconds + 0.1, end_seconds) * self.sample_rate)
                self._loop_label = label
            current_state = self._loop_enabled
        self._notify_tick()
        return current_state

    def get_loop_state(self) -> dict:
        """Retorna el estado actual de bucle y saltos programados."""
        with self._lock:
            jump_sec = round(self._pending_jump_frame / self.sample_rate, 2) if self._pending_jump_frame is not None else None
            trans_sec = round(self._jump_target_bar_frame / self.sample_rate, 2) if self._jump_target_bar_frame is not None else None
            return {
                "loop_enabled": self._loop_enabled,
                "loop_active": self._loop_enabled,
                "loop_label": self._loop_label,
                "loop_section": self._loop_label,
                "loop_start": round(self._loop_start_frame / self.sample_rate, 2),
                "loop_end": round(self._loop_end_frame / self.sample_rate, 2),
                "pending_jump": self._pending_jump_label or (str(jump_sec) if jump_sec is not None else None),
                "pending_jump_label": self._pending_jump_label,
                "jump_target": jump_sec,
                "jump_transition_at": trans_sec,
            }

    def register_track_finished_listener(self, callback: Callable[[], None]) -> None:
        """Registra un callback invocado cuando la pista termina de reproducirse."""
        if callback not in self._track_finished_callbacks:
            self._track_finished_callbacks.append(callback)

    def _notify_track_finished(self) -> None:
        """Notifica a los suscriptores que la pista de audio finalizó."""
        for cb in self._track_finished_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _mix_stems_range(
        self,
        master_out: np.ndarray,
        cue_out: np.ndarray,
        start_frame: int,
        num_frames: int,
        has_solo: bool,
    ) -> None:
        """Mezcla un rango de frames en los buffers especificados."""
        for stem in self._stems.values():
            if has_solo and not stem.solo:
                continue
            if stem.mute:
                continue
            route = stem.route
            if route in ("master", "both"):
                stem.add_slice_to(master_out, start_frame, num_frames)
            if route in ("cue", "both"):
                stem.add_slice_to(cue_out, start_frame, num_frames)

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
        Mezcla los stems activos según su volumen, mute, solo y asignación de ruteo
        utilizando acumulación in-place sin asignaciones de memoria (Zero-Allocation).
        """
        outdata.fill(0.0)

        if not self._is_playing:
            with self._lock:
                if self._active_overlay_cue is None:
                    return
                # Inyección de guía de voz en in-ears aún en pausa (para soundcheck / aviso previo)
                if len(self._cue_mix_buf) < frames:
                    self._master_mix_buf = np.zeros((frames, 2), dtype=np.float32)
                    self._cue_mix_buf = np.zeros((frames, 2), dtype=np.float32)
                cue_mix = self._cue_mix_buf[:frames]
                cue_mix.fill(0.0)
                rem_cue = len(self._active_overlay_cue) - self._active_overlay_pos
                if rem_cue > 0:
                    copy_len = min(frames, rem_cue)
                    cue_chunk = self._active_overlay_cue[self._active_overlay_pos : self._active_overlay_pos + copy_len]
                    cue_mix[:copy_len, 0] = cue_chunk * 1.25
                    cue_mix[:copy_len, 1] = cue_chunk * 1.25
                    self._active_overlay_pos += copy_len
                    if self._active_overlay_pos >= len(self._active_overlay_cue):
                        self._active_overlay_cue = None
                        self._active_overlay_pos = 0
                else:
                    self._active_overlay_cue = None
                    self._active_overlay_pos = 0

                if self.routing_mode == RoutingMode.SPLIT_STEREO:
                    cue_mono = (cue_mix[:, 0] + cue_mix[:, 1]) * (0.5 * self._cue_volume)
                    outdata[:, 0] = np.clip(cue_mono, -1.0, 1.0)
                    outdata[:, 1] = 0.0
                else:
                    cue_out = cue_mix * self._cue_volume
                    outdata[:, 0] = np.clip(cue_out[:, 0], -1.0, 1.0)
                    outdata[:, 1] = np.clip(cue_out[:, 1], -1.0, 1.0)
                return

        with self._lock:
            curr = self._current_frame
            max_frames = self.total_frames

            # 1. Comprobar si llegamos al final de la canción
            if curr >= max_frames and not self._loop_enabled:
                self._is_playing = False
                track_finished = True
            else:
                track_finished = False

            if track_finished:
                threading.Thread(target=self._notify_track_finished, daemon=True).start()
                return

            # Reutilizar buffers preasignados evitando allocs de NumPy por cada bloque
            if len(self._master_mix_buf) < frames:
                self._master_mix_buf = np.zeros((frames, 2), dtype=np.float32)
                self._cue_mix_buf = np.zeros((frames, 2), dtype=np.float32)

            master_mix = self._master_mix_buf[:frames]
            cue_mix = self._cue_mix_buf[:frames]
            master_mix.fill(0.0)
            cue_mix.fill(0.0)

            has_solo = any(stem.solo for stem in self._stems.values())

            # 2. Detección de Transición Cuantizada al Compás o Bucle Activo
            samples_per_beat = max(1, int((60.0 / max(10.0, self._bpm)) * self.sample_rate))
            samples_per_bar = max(1, samples_per_beat * self._beats_per_bar)

            transition_frame = None
            target_frame = None

            # Caso A: Salto programado con compás completo de espera y conteo rítmico ("Coro 2, 3, 4")
            if self._jump_lead_bar_frame is not None:
                if curr <= self._jump_lead_bar_frame < curr + frames:
                    if self._dynamic_cues_enabled and self._pending_jump_label:
                        lead_cue = self._cue_manager.build_transition_cue(
                            self._pending_jump_label, bpm=self._bpm, beats_per_bar=self._beats_per_bar
                        )
                        if lead_cue is not None:
                            self._active_overlay_cue = lead_cue
                            self._active_overlay_pos = 0
                    self._jump_lead_bar_frame = None

            if self._jump_target_bar_frame is not None and self._pending_jump_frame is not None:
                if curr <= self._jump_target_bar_frame < curr + frames:
                    transition_frame = self._jump_target_bar_frame
                    target_frame = self._pending_jump_frame
                    self._jump_target_bar_frame = None
                    self._pending_jump_frame = None
                    self._pending_jump_label = ""
            elif self._pending_jump_frame is not None and self._jump_target_bar_frame is None:
                bar_idx = curr // samples_per_bar
                next_bar = (bar_idx + 1) * samples_per_bar
                if curr <= next_bar < curr + frames:
                    transition_frame = next_bar
                    target_frame = self._pending_jump_frame
                    self._pending_jump_frame = None
                    self._pending_jump_label = ""
            # Caso B: Bucle infinito de sección activo
            elif self._loop_enabled and self._loop_end_frame > self._loop_start_frame:
                if curr < self._loop_end_frame <= curr + frames:
                    transition_frame = self._loop_end_frame
                    target_frame = self._loop_start_frame

            # Detección de aviso de bucle en In-Ears: 1 compás antes de volver a repetir la sección
            if self._loop_enabled and self._dynamic_cues_enabled and self._loop_label:
                loop_lead = self._loop_end_frame - samples_per_bar
                if loop_lead <= curr < self._loop_end_frame:
                    if self._loop_cue_last_fired_frame != self._loop_end_frame:
                        self._loop_cue_last_fired_frame = self._loop_end_frame
                        loop_cue_audio = self._cue_manager.build_loop_cue(self._loop_label)
                        if loop_cue_audio is not None:
                            self._active_overlay_cue = loop_cue_audio
                            self._active_overlay_pos = 0
                elif curr < loop_lead - samples_per_bar or curr >= self._loop_end_frame:
                    self._loop_cue_last_fired_frame = -1

            if transition_frame is not None and target_frame is not None:
                split = max(0, min(frames, transition_frame - curr))
                # Mezclar parte 1 (antes del límite de compás)
                if split > 0:
                    self._mix_stems_range(master_mix[:split], cue_mix[:split], curr, split, has_solo)
                # Mezclar parte 2 (después del límite de compás en el nuevo punto)
                rem = frames - split
                if rem > 0:
                    self._mix_stems_range(master_mix[split:frames], cue_mix[split:frames], target_frame, rem, has_solo)

                # Micro-crossfade isopotente (15 ms) en la costura para evitar 'clics' o 'pops'
                fade_k = min(self._fade_len, split, rem)
                if fade_k > 8:
                    t = np.linspace(0.0, 1.0, fade_k, dtype=np.float32)[:, np.newaxis]
                    f_out = 0.5 * (1.0 + np.cos(np.pi * t))
                    f_in = 0.5 * (1.0 - np.cos(np.pi * t))
                    master_mix[split - fade_k : split] *= f_out
                    cue_mix[split - fade_k : split] *= f_out
                    master_mix[split : split + fade_k] *= f_in
                    cue_mix[split : split + fade_k] *= f_in

                self._current_frame = target_frame + rem
            else:
                self._mix_stems_range(master_mix, cue_mix, curr, frames, has_solo)
                self._current_frame += frames

            # Inyección de Guías de Audio Dinámicas en el canal CUE / In-Ear (nunca en FOH / Sala)
            if self._active_overlay_cue is not None:
                rem_cue = len(self._active_overlay_cue) - self._active_overlay_pos
                if rem_cue > 0:
                    copy_len = min(frames, rem_cue)
                    cue_chunk = self._active_overlay_cue[self._active_overlay_pos : self._active_overlay_pos + copy_len]
                    cue_mix[:copy_len, 0] += cue_chunk * 1.25
                    cue_mix[:copy_len, 1] += cue_chunk * 1.25
                    self._active_overlay_pos += copy_len
                    if self._active_overlay_pos >= len(self._active_overlay_cue):
                        self._active_overlay_cue = None
                        self._active_overlay_pos = 0
                else:
                    self._active_overlay_cue = None
                    self._active_overlay_pos = 0

            # Aplicación de modo de ruteo con aceleración vectorizada
            if self.routing_mode == RoutingMode.SPLIT_STEREO:
                # Canal 0 (Izquierdo / L) = Monitores In-Ears (Click + Guía + banda)
                cue_mono = (cue_mix[:, 0] + cue_mix[:, 1]) * (0.5 * self._cue_volume)
                # Canal 1 (Derecho / R) = Consola FOH (Solo instrumentos, JAMÁS click ni guía)
                master_mono = (master_mix[:, 0] + master_mix[:, 1]) * (0.5 * self._master_volume)

                outdata[:, 0] = np.clip(cue_mono, -1.0, 1.0)
                outdata[:, 1] = np.clip(master_mono, -1.0, 1.0)
            else:
                # Modo Estéreo Normal: Mezcla completa en ambos canales
                full_l = (master_mix[:, 0] * self._master_volume) + (cue_mix[:, 0] * self._cue_volume)
                full_r = (master_mix[:, 1] * self._master_volume) + (cue_mix[:, 1] * self._cue_volume)
                outdata[:, 0] = np.clip(full_l, -1.0, 1.0)
                outdata[:, 1] = np.clip(full_r, -1.0, 1.0)

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
        """Bucle periódico a ~22 Hz (cada 45 ms) para sincronizar red sin sobrecargar el CPU."""
        while not self._stop_ticker_event.is_set() and self._is_playing:
            self._notify_tick()
            time.sleep(0.045)

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
