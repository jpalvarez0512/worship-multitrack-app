"""
Gestor de Escenas / Listas de Servicio Dominical (Setlists)
Permite armar repertorios con fecha, nombre, notas y orden de canciones a partir de la Biblioteca.
"""

import json
import os
import threading
from datetime import datetime
from typing import Dict, List, Optional
from src.core.chordpro import slugify


class SceneManager:
    """Administra las escenas (listas de canciones por fecha/servicio) en config/scenes.json."""

    def __init__(self, scenes_file: str):
        self.scenes_file = os.path.abspath(scenes_file)
        os.makedirs(os.path.dirname(self.scenes_file), exist_ok=True)
        self._lock = threading.RLock()
        if not os.path.exists(self.scenes_file):
            self._save_raw([])

    def _load_raw(self) -> List[dict]:
        if not os.path.exists(self.scenes_file):
            return []
        try:
            with open(self.scenes_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_raw(self, scenes: List[dict]) -> None:
        with open(self.scenes_file, "w", encoding="utf-8") as f:
            json.dump(scenes, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _normalize_songs(songs: Optional[List]) -> List[dict]:
        normalized = []
        for item in songs or []:
            if isinstance(item, str):
                song_id = item.strip()
                transpose = 0
                subgroup = ""
                auto_next = False
            elif isinstance(item, dict):
                song_id = str(item.get("song_id") or item.get("id") or "").strip()
                try:
                    transpose = int(item.get("transpose", 0))
                except (TypeError, ValueError):
                    transpose = 0
                subgroup = str(item.get("subgroup") or "").strip()
                auto_next = bool(item.get("auto_next", False))
            else:
                continue
            if song_id:
                normalized.append({
                    "song_id": song_id,
                    "transpose": transpose,
                    "subgroup": subgroup,
                    "auto_next": auto_next,
                })
        return normalized

    @staticmethod
    def _enrich_scene(scene: dict, library_map: Optional[Dict[str, dict]] = None) -> dict:
        enriched = dict(scene)
        items = []
        for idx, entry in enumerate(scene.get("songs", [])):
            sid = entry.get("song_id", "")
            transpose = int(entry.get("transpose", 0))
            subgroup = entry.get("subgroup", "")
            auto_next = bool(entry.get("auto_next", False))
            info = (library_map or {}).get(sid)
            if info:
                items.append({
                    "index": idx,
                    "song_id": sid,
                    "transpose": transpose,
                    "subgroup": subgroup,
                    "auto_next": auto_next,
                    "title": info.get("title", sid),
                    "artist": info.get("artist", ""),
                    "key": info.get("key", "C"),
                    "bpm": info.get("bpm", 120),
                    "duration": info.get("duration", 0.0),
                    "stems_count": info.get("stems_count", 0),
                    "missing": False,
                })
            else:
                items.append({
                    "index": idx,
                    "song_id": sid,
                    "transpose": transpose,
                    "subgroup": subgroup,
                    "auto_next": auto_next,
                    "title": sid.replace("-", " ").title(),
                    "artist": "",
                    "key": "-",
                    "bpm": 0,
                    "duration": 0.0,
                    "stems_count": 0,
                    "missing": library_map is not None,
                })
        enriched["items"] = items
        enriched["songs_count"] = len(items)
        return enriched

    def list_scenes(self, library_map: Optional[Dict[str, dict]] = None) -> List[dict]:
        with self._lock:
            scenes = self._load_raw()
        scenes.sort(key=lambda s: (s.get("date") or "", s.get("name") or ""), reverse=True)
        return [self._enrich_scene(s, library_map) for s in scenes]

    def get_scene(self, scene_id: str, library_map: Optional[Dict[str, dict]] = None) -> dict:
        with self._lock:
            for s in self._load_raw():
                if s.get("id") == scene_id:
                    return self._enrich_scene(s, library_map)
        raise KeyError(f"Escena no encontrada: {scene_id}")

    def create_scene(
        self,
        name: str,
        date: str = "",
        notes: str = "",
        songs: Optional[List] = None,
    ) -> dict:
        clean_name = (name or "").strip() or "Servicio Dominical"
        clean_date = (date or "").strip() or datetime.now().strftime("%Y-%m-%d")
        base_id = slugify(f"{clean_date}-{clean_name}") or "escena"

        with self._lock:
            scenes = self._load_raw()
            existing_ids = {s.get("id") for s in scenes}
            scene_id = base_id
            counter = 2
            while scene_id in existing_ids:
                scene_id = f"{base_id}-{counter}"
                counter += 1

            new_scene = {
                "id": scene_id,
                "name": clean_name,
                "date": clean_date,
                "notes": (notes or "").strip(),
                "songs": self._normalize_songs(songs),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            scenes.append(new_scene)
            self._save_raw(scenes)
            return self._enrich_scene(new_scene)

    def update_scene(
        self,
        scene_id: str,
        name: Optional[str] = None,
        date: Optional[str] = None,
        notes: Optional[str] = None,
        songs: Optional[List] = None,
    ) -> dict:
        with self._lock:
            scenes = self._load_raw()
            for s in scenes:
                if s.get("id") == scene_id:
                    if name is not None and name.strip():
                        s["name"] = name.strip()
                    if date is not None:
                        s["date"] = date.strip()
                    if notes is not None:
                        s["notes"] = notes.strip()
                    if songs is not None:
                        s["songs"] = self._normalize_songs(songs)
                    self._save_raw(scenes)
                    return self._enrich_scene(s)
        raise KeyError(f"Escena no encontrada: {scene_id}")

    def delete_scene(self, scene_id: str) -> None:
        with self._lock:
            scenes = self._load_raw()
            remaining = [s for s in scenes if s.get("id") != scene_id]
            if len(remaining) == len(scenes):
                raise KeyError(f"Escena no encontrada: {scene_id}")
            self._save_raw(remaining)
