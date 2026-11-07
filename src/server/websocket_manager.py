"""
Gestor Central de Conexiones WebSocket y Distribución en Tiempo Real
Subagente responsable: 03-network-sync-engineer
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Set
from fastapi import WebSocket


class ChannelType:
    MUSICIANS = "musicians"
    PROJECTION = "projection"
    CONTROL = "control"


class ConnectionManager:
    """
    Gestiona las conexiones WebSocket activas agrupadas por rol (músicos, proyección, operador)
    y realiza la distribución de estado de baja latencia con compensación de reloj.
    """

    def __init__(self):
        # Mapeo de categoría a conjunto de websockets
        self._channels: Dict[str, Set[WebSocket]] = {
            ChannelType.MUSICIANS: set(),
            ChannelType.PROJECTION: set(),
            ChannelType.CONTROL: set(),
        }
        # Metadatos por conexión (ej. transposición personalizada por músico)
        self._client_transpositions: Dict[WebSocket, int] = {}
        # Estado de proyección (blackout / texto oculto)
        self._projection_blackout: bool = False
        self._projection_clear_text: bool = False

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """Acepta y registra una nueva conexión de cliente en el canal especificado."""
        await websocket.accept()
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(websocket)
        self._client_transpositions[websocket] = 0

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        """Elimina una conexión cerrada."""
        if channel in self._channels and websocket in self._channels[channel]:
            self._channels[channel].remove(websocket)
        self._client_transpositions.pop(websocket, None)

    def set_client_transposition(self, websocket: WebSocket, semitones: int) -> None:
        """Ajusta la transposición personal de un músico (ej. saxofón o capo de guitarra)."""
        self._client_transpositions[websocket] = semitones

    def set_projection_state(self, blackout: Optional[bool] = None, clear_text: Optional[bool] = None) -> None:
        """Modifica el estado visual de la pantalla de proyección."""
        if blackout is not None:
            self._projection_blackout = blackout
        if clear_text is not None:
            self._projection_clear_text = clear_text

    async def broadcast_to_channel(self, channel: str, message: dict) -> None:
        """Envía un mensaje a todos los clientes suscritos a un canal específico."""
        clients = list(self._channels.get(channel, set()))
        if not clients:
            return

        payload = json.dumps(message)
        dead_clients = []
        for ws in clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_clients.append(ws)

        for dead in dead_clients:
            self.disconnect(dead, channel)

    async def broadcast_tick(
        self,
        position_seconds: float,
        is_playing: bool,
        current_section: str = "",
        next_section: str = "",
        current_lyric: str = "",
        current_chord: str = "",
        projection_lyric: Optional[str] = None,
        projection_section: Optional[str] = None,
        loop_active: bool = False,
        loop_section: str = "",
        pending_jump: str = "",
        bars_remaining: int = 0,
    ) -> None:
        """
        Emite la actualización periódica del reloj a todos los canales
        optimizando el payload para cada audiencia.
        """
        now = time.time()

        # 1. Canal de Músicos: tiempo exacto, compás, acordes, letra y bucle espontáneo
        if self._channels[ChannelType.MUSICIANS]:
            musician_payload = {
                "type": "tick",
                "pos": round(position_seconds, 3),
                "playing": is_playing,
                "sec": current_section,
                "next": next_section,
                "chord": current_chord,
                "lyric": current_lyric,
                "loop_active": loop_active,
                "loop_sec": loop_section,
                "jump_pending": pending_jump,
                "bars_remaining": bars_remaining,
                "server_time": now,
            }
            await self.broadcast_to_channel(ChannelType.MUSICIANS, musician_payload)

        # 2. Canal de Proyección: letra limpia con anticipación de lectura y estado visual
        if self._channels[ChannelType.PROJECTION]:
            proj_txt = current_lyric if projection_lyric is None else projection_lyric
            proj_sec = current_section if projection_section is None else projection_section
            projection_payload = {
                "type": "projection_tick",
                "pos": round(position_seconds, 3),
                "playing": is_playing,
                "sec": proj_sec,
                "lyric": "" if self._projection_clear_text else proj_txt,
                "blackout": self._projection_blackout,
                "clear": self._projection_clear_text,
            }
            await self.broadcast_to_channel(ChannelType.PROJECTION, projection_payload)

        # 3. Canal de Operador / Control
        if self._channels[ChannelType.CONTROL]:
            control_payload = {
                "type": "control_tick",
                "pos": round(position_seconds, 3),
                "playing": is_playing,
                "sec": current_section,
                "loop_active": loop_active,
                "loop_sec": loop_section,
                "jump_pending": pending_jump,
                "bars_remaining": bars_remaining,
            }
            await self.broadcast_to_channel(ChannelType.CONTROL, control_payload)

    async def handle_client_message(self, websocket: WebSocket, channel: str, data: dict, current_song_pos: float, is_playing: bool) -> None:
        """
        Procesa mensajes entrantes desde los clientes (ping de sincronización, transposición, etc.).
        """
        msg_type = data.get("type")

        # Mini-NTP Clock Sync: Permite al cliente calcular latencia de red y offset exacto
        if msg_type == "sync_ping":
            client_t0 = data.get("client_time", 0.0)
            now = time.time()
            response = {
                "type": "sync_pong",
                "client_time": client_t0,
                "server_time": now,
                "song_pos": round(current_song_pos, 3),
                "playing": is_playing,
            }
            await websocket.send_text(json.dumps(response))

        elif msg_type == "set_transpose":
            semitones = int(data.get("semitones", 0))
            self.set_client_transposition(websocket, semitones)
            await websocket.send_text(
                json.dumps({"type": "transpose_updated", "semitones": semitones})
            )

        elif msg_type == "set_projection":
            blackout = data.get("blackout")
            clear_text = data.get("clear")
            self.set_projection_state(blackout=blackout, clear_text=clear_text)
            # Notificar de inmediato al canal de proyección
            await self.broadcast_to_channel(
                ChannelType.PROJECTION,
                {
                    "type": "projection_state",
                    "blackout": self._projection_blackout,
                    "clear": self._projection_clear_text,
                },
            )

    @property
    def total_clients(self) -> int:
        return sum(len(clients) for clients in self._channels.values())

    def get_stats(self) -> dict:
        return {
            "musicians_connected": len(self._channels[ChannelType.MUSICIANS]),
            "projection_screens": len(self._channels[ChannelType.PROJECTION]),
            "controllers": len(self._channels[ChannelType.CONTROL]),
            "total_connected": self.total_clients,
        }
