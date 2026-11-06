"""
Gestor de Guías de Audio Dinámicas (Cues en Español) para Monitores In-Ear
Permite inyectar avisos hablados en tiempo real ante saltos cuantizados y bucles de adoración espontánea.
"""

import os
import wave
from typing import Dict, Optional
import numpy as np


class CueManager:
    """Carga y administra el banco de voces de guía en memoria."""

    def __init__(self, cues_dir: Optional[str] = None, sample_rate: int = 44100):
        if cues_dir is None:
            cues_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "assets", "cues")
            )
        self.cues_dir = cues_dir
        self.sample_rate = sample_rate
        self._cues: Dict[str, np.ndarray] = {}
        self.load_cues()

    def load_cues(self) -> None:
        """Carga todos los archivos .wav en memoria como arreglos NumPy float32."""
        if not os.path.exists(self.cues_dir):
            return

        for fname in os.listdir(self.cues_dir):
            if fname.lower().endswith(".wav"):
                name = os.path.splitext(fname)[0].lower()
                full_path = os.path.join(self.cues_dir, fname)
                try:
                    with wave.open(full_path, "rb") as wf:
                        n_ch = wf.getnchannels()
                        sampwidth = wf.getsampwidth()
                        sr = wf.getframerate()
                        frames = wf.readframes(wf.getnframes())

                    if sampwidth == 2:
                        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                    else:
                        data = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

                    if n_ch == 2:
                        data = data.reshape(-1, 2).mean(axis=1)

                    # Si difiere la frecuencia de muestreo, resamplear linealmente de forma rápida
                    if sr != self.sample_rate and len(data) > 0:
                        target_len = int(len(data) * (self.sample_rate / sr))
                        x_old = np.linspace(0, 1, len(data))
                        x_new = np.linspace(0, 1, target_len)
                        data = np.interp(x_new, x_old, data).astype(np.float32)

                    self._cues[name] = data
                except Exception as e:
                    print(f"⚠️ Error cargando cue {fname}: {e}")

    def get_cue(self, name: str) -> Optional[np.ndarray]:
        """Devuelve el audio de un cue por su clave directa (ej. 'coro', 'puente')."""
        return self._cues.get(name.lower().strip())

    def match_section_cue_name(self, section_name: str) -> str:
        """Asocia el nombre de una sección musical (en español o inglés) con el cue correspondiente."""
        s = section_name.lower().strip()
        if "intro" in s:
            return "intro"
        if "pre" in s and ("coro" in s or "chorus" in s):
            return "pre_coro"
        if "coro" in s or "chorus" in s:
            return "coro"
        if "puente" in s or "bridge" in s:
            return "puente"
        if "instrumental" in s or "interludio" in s:
            return "instrumental"
        if "solo" in s:
            return "solo"
        if "final" in s or "outro" in s:
            return "final"
        if "verso 1" in s or "verso uno" in s or "verse 1" in s:
            return "verso_1"
        if "verso 2" in s or "verso dos" in s or "verse 2" in s:
            return "verso_2"
        if "verso" in s or "verse" in s:
            return "verso"
        return ""

    def get_cue_for_section(self, section_name: str) -> Optional[np.ndarray]:
        """Devuelve el audio de la sección especificada."""
        cue_name = self.match_section_cue_name(section_name)
        if cue_name:
            return self.get_cue(cue_name)
        return None

    def build_loop_cue(self, section_name: str) -> Optional[np.ndarray]:
        """
        Construye una guía compuesta para bucle espontáneo:
        'Repite' + silencio breve (80 ms) + [Nombre de la Sección].
        """
        repite = self.get_cue("repite")
        sec_cue = self.get_cue_for_section(section_name)

        if repite is not None and sec_cue is not None:
            gap = np.zeros(int(self.sample_rate * 0.08), dtype=np.float32)
            return np.concatenate([repite, gap, sec_cue])
        elif sec_cue is not None:
            return sec_cue
        elif repite is not None:
            return repite
        return None
