"""
Modulo de Cuantizacion Armonica al Pulso Musical
Worship Multitrack Live
Alinea con precision milimetrica los cambios de acorde al pulso o compas
mas cercano de la rejilla ritmica (+/- 120 ms), corrigiendo anticipaciones o retrasos vocales.
"""

from typing import List, Tuple
from src.audio.rhythmic_grid import RhythmicGrid
from src.core.song import ChordMarker, Song, SongLine, SongSection


def quantize_chord_marker(
    marker: ChordMarker,
    grid: RhythmicGrid,
    tolerance: float = 0.120,
) -> ChordMarker:
    """
    Cuantiza un marcador de acorde al pulso musical mas cercano dentro de la tolerancia.
    """
    snapped = grid.snap_to_nearest_beat(marker.time, max_tolerance=tolerance)
    return ChordMarker(
        time=snapped,
        chord=marker.chord,
        char_offset=marker.char_offset,
    )


def quantize_song_line(
    line: SongLine,
    grid: RhythmicGrid,
    tolerance: float = 0.120,
) -> SongLine:
    """
    Cuantiza los acordes y ajusta los extremos temporales de una linea de cancion.
    """
    # Ajustar tiempo de inicio al pulso o compas mas cercano
    snapped_start = grid.snap_to_nearest_beat(line.start_time, max_tolerance=tolerance)
    snapped_end = grid.snap_to_nearest_beat(line.end_time, max_tolerance=tolerance)

    if snapped_end <= snapped_start:
        snapped_end = snapped_start + grid.beat_duration

    new_chords = [
        quantize_chord_marker(c, grid, tolerance=tolerance)
        for c in line.chords
    ]

    return SongLine(
        start_time=round(snapped_start, 3),
        end_time=round(snapped_end, 3),
        lyrics=line.lyrics,
        chords=new_chords,
    )


def quantize_song(
    song: Song,
    grid: RhythmicGrid,
    tolerance: float = 0.120,
) -> Song:
    """
    Aplica cuantizacion ritmica a todas las secciones y lineas de una cancion.
    """
    new_sections = []
    for sec in song.sections:
        # Inicio de seccion preferentemente anclado a compas (downbeat)
        sec_start = grid.snap_to_nearest_downbeat(sec.start_time, max_tolerance=0.250)
        sec_end = grid.snap_to_nearest_downbeat(sec.end_time, max_tolerance=0.250)
        if sec_end <= sec_start:
            sec_end = sec_start + grid.bar_duration

        quantized_lines = [
            quantize_song_line(line, grid, tolerance=tolerance)
            for line in sec.lines
        ]

        new_sections.append(
            SongSection(
                name=sec.name,
                start_time=round(sec_start, 3),
                end_time=round(sec_end, 3),
                lines=quantized_lines,
            )
        )

    # Ordenar y asegurar no solapamiento
    new_sections.sort(key=lambda s: s.start_time)
    for i in range(len(new_sections) - 1):
        if new_sections[i].end_time > new_sections[i + 1].start_time:
            new_sections[i].end_time = new_sections[i + 1].start_time

    return Song(
        id=song.id,
        title=song.title,
        artist=song.artist,
        key=song.key,
        bpm=round(grid.bpm, 2),
        time_signature=grid.time_signature,
        sections=new_sections,
    )
