"""
Módulo de Verificación de Actualizaciones y Preservación de Datos Locales
Permite consultar GitHub Releases para detectar nuevas versiones y mantener la app al día
sin tocar nunca las carpetas locales de usuario (tracks/, config/, assets/).
"""

import json
import re
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

CURRENT_VERSION = "2.1.0"
GITHUB_REPO = "jpalvarez0512/worship-multitrack-app"


def _parse_version(v_str: str) -> Tuple[int, ...]:
    """Extrae tupla numérica de versiones como 'v2.1.0' o '2.0.4'."""
    clean = re.sub(r"[^\d.]", "", v_str or "")
    if not clean:
        return (0, 0, 0)
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def check_for_updates(timeout_seconds: float = 2.5) -> Dict:
    """
    Consulta la API pública de GitHub para verificar si existe una versión más reciente.
    Retorna información estructurada de forma silenciosa y segura ante fallos de red.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"WorshipMultitrackApp/{CURRENT_VERSION}",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    result = {
        "current_version": CURRENT_VERSION,
        "latest_version": CURRENT_VERSION,
        "update_available": False,
        "release_name": "",
        "release_notes": "",
        "download_url": f"https://github.com/{GITHUB_REPO}",
        "offline": False,
    }

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                tag = data.get("tag_name", "").strip()
                latest_tuple = _parse_version(tag)
                current_tuple = _parse_version(CURRENT_VERSION)

                result["latest_version"] = tag.lstrip("v") if tag else CURRENT_VERSION
                result["update_available"] = latest_tuple > current_tuple
                result["release_name"] = data.get("name", "") or tag
                result["release_notes"] = data.get("body", "").strip()
                result["download_url"] = data.get("html_url", result["download_url"])
                return result
    except urllib.error.HTTPError as e:
        # Si 404 (aún no se publicó release formal), consultar los tags
        if e.code == 404:
            return _check_tags(timeout_seconds=timeout_seconds, base_result=result)
        result["offline"] = True
    except Exception:
        result["offline"] = True

    return result


def _check_tags(timeout_seconds: float = 2.5, base_result: Optional[Dict] = None) -> Dict:
    """Verificación secundaria mediante tags de git."""
    result = base_result or {
        "current_version": CURRENT_VERSION,
        "latest_version": CURRENT_VERSION,
        "update_available": False,
        "offline": False,
    }
    url = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"WorshipMultitrackApp/{CURRENT_VERSION}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status == 200:
                tags = json.loads(response.read().decode("utf-8"))
                if tags and isinstance(tags, list):
                    first_tag = tags[0].get("name", "")
                    latest_tuple = _parse_version(first_tag)
                    current_tuple = _parse_version(CURRENT_VERSION)
                    result["latest_version"] = first_tag.lstrip("v")
                    result["update_available"] = latest_tuple > current_tuple
    except Exception:
        result["offline"] = True
    return result
