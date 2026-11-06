"""
Generador de Banco de Voces de Guía (Cues) para In-Ears en Español.
Utiliza el motor de síntesis de voz de Windows (Microsoft Helena Desktop / es-ES)
para producir archivos WAV limpios, sin latencia y con calidad de estudio.
"""

import os
import subprocess
import sys
import wave
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CUES_DIR = os.path.join(ROOT_DIR, "assets", "cues")
os.makedirs(CUES_DIR, exist_ok=True)

# Lista de indicaciones musicales clave para el culto
CUES = {
    "intro": "Intro",
    "verso": "Verso",
    "verso_1": "Verso uno",
    "verso_2": "Verso dos",
    "pre_coro": "Pre coro",
    "coro": "Coro",
    "puente": "Puente",
    "instrumental": "Instrumental",
    "solo": "Solo",
    "final": "Final",
    "repite": "Repite",
    "atentos": "Atentos",
    "corte": "Corte",
    "uno": "Uno",
    "dos": "Dos",
    "tres": "Tres",
    "cuatro": "Cuatro",
}


def generate_cue_wav_powershell(name: str, phrase: str, target_path: str):
    """Invoca PowerShell System.Speech.Synthesis para generar el archivo WAV con voz en español."""
    ps_cmd = f"""
    Add-Type -AssemblyName System.Speech
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $voice = $synth.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq 'es' }} | Select-Object -First 1
    if ($voice) {{
        $synth.SelectVoice($voice.VoiceInfo.Name)
    }}
    $synth.Rate = 2  # Velocidad ajustada para sincronización rítmica precisa
    $synth.SetOutputToWaveFile('{target_path}')
    $synth.Speak('{phrase}')
    $synth.Dispose()
    """
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Error generando cue '{name}': {res.stderr}")


def optimize_wav(path: str):
    """Normaliza el pico de audio y recorta silencios para un impacto nítido en el in-ear."""
    with wave.open(path, "rb") as wf:
        n_ch = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sampwidth == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        audio = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

    if n_ch == 2:
        audio = audio.reshape(-1, 2).mean(axis=1)

    # Recortar silencio inicial y final (> -36 dB)
    threshold = 0.015
    active_indices = np.where(np.abs(audio) > threshold)[0]
    if len(active_indices) > 0:
        start_idx = max(0, active_indices[0] - int(sr * 0.02))  # 20ms pre-roll
        end_idx = min(len(audio), active_indices[-1] + int(sr * 0.05))  # 50ms post-roll
        audio = audio[start_idx:end_idx]

    # Normalizar volumen pico a -1.0 dB
    peak = np.max(np.abs(audio))
    if peak > 1e-4:
        audio = (audio / peak) * 0.89  # -1 dBFS

    # Guardar como WAV mono de 16-bit PCM a la misma frecuencia de muestreo
    pcm16 = (audio * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())


def generate_all_cues():
    print(f"🎙️ Generando {len(CUES)} guías de voz en español en {CUES_DIR}...")
    for key, phrase in CUES.items():
        out_file = os.path.join(CUES_DIR, f"{key}.wav")
        generate_cue_wav_powershell(key, phrase, out_file)
        optimize_wav(out_file)
        size_kb = os.path.getsize(out_file) / 1024
        print(f"  ✓ {key}.wav ('{phrase}') -> {size_kb:.1f} KB")
    print("✅ Banco completo de guías de audio generado con éxito.")


if __name__ == "__main__":
    generate_all_cues()
