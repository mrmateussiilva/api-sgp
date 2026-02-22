"""
Chat em tempo real via WebSocket.
Gerencia conexões, lista de online e broadcast de mensagens.
Segue o mesmo padrão de pedidos/realtime.py (OrdersNotifier).

IMPORTANTE: rastreia conexões por user_id para permitir múltiplas
conexões do mesmo usuário sem gerar eventos duplicados de join/leave.
"""
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Set, Optional

import orjson
from fastapi import WebSocket


class ChatNotifier:
    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        # Rastrear conexões por user_id (múltiplas conexões permitidas)
        self._connections_by_user: Dict[int, Set[WebSocket]] = defaultdict(set)
        # Metadados por WebSocket
        self._meta: Dict[WebSocket, Dict[str, Any]] = {}
        # Metadados por user_id (para lista de online — mantém o primeiro connected_at)
        self._user_info: Dict[int, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_interval = 30
        self._heartbeat_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Conexão / Desconexão
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket, user_id: int, username: str) -> None:
        """Registra conexão. Só emite user_joined se for a PRIMEIRA conexão do user_id."""
        connected_at = datetime.now(timezone.utc).isoformat()
        is_new_user = False

        async with self._lock:
            self._connections.add(websocket)
            self._meta[websocket] = {
                "user_id": user_id,
                "username": username,
                "connected_at": connected_at,
            }

            # Verificar se é a primeira conexão deste user_id
            is_new_user = len(self._connections_by_user[user_id]) == 0
            self._connections_by_user[user_id].add(websocket)

            if is_new_user:
                self._user_info[user_id] = {
                    "username": username,
                    "connected_at": connected_at,
                }

        if __debug__:
            total_conns = len(self._connections)
            user_conns = len(self._connections_by_user[user_id])
            print(f"[Chat] Conexão: {username} (user_id={user_id}, conns_user={user_conns}, total={total_conns}, new={is_new_user})")

        # Enviar lista de online para o novo cliente
        users_list = self._build_users_list()
        await self._send(websocket, {"type": "users_list", "users": users_list})

        # Só notificar user_joined se for realmente um novo usuário
        if is_new_user:
            await self.broadcast_except(
                {
                    "type": "user_joined",
                    "user": {
                        "userId": user_id,
                        "username": username,
                        "connectedAt": connected_at,
                    },
                },
                exclude_websocket=websocket,
            )

        # Iniciar heartbeat
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove conexão. Só emite user_left se for a ÚLTIMA conexão do user_id."""
        meta = None
        is_last_connection = False

        async with self._lock:
            if websocket in self._connections:
                meta = self._meta.pop(websocket, None)
                self._connections.discard(websocket)

                if meta:
                    user_id = meta["user_id"]
                    self._connections_by_user[user_id].discard(websocket)
                    if not self._connections_by_user[user_id]:
                        del self._connections_by_user[user_id]
                        self._user_info.pop(user_id, None)
                        is_last_connection = True

        if meta:
            if __debug__:
                remaining = len(self._connections_by_user.get(meta["user_id"], set()))
                print(f"[Chat] Desconexão: {meta['username']} (remaining={remaining}, last={is_last_connection}, total={len(self._connections)})")

            # Só notificar user_left se era a última conexão deste user_id
            if is_last_connection:
                await self.broadcast(
                    {
                        "type": "user_left",
                        "user": {
                            "userId": meta["user_id"],
                            "username": meta["username"],
                        },
                    }
                )

    # ------------------------------------------------------------------
    # Broadcast
    # ------------------------------------------------------------------

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Envia mensagem para todos os clientes conectados."""
        async with self._lock:
            recipients = list(self._connections)

        if not recipients:
            return

        payload = self._serialize(message)
        if payload is None:
            return

        stale: Set[WebSocket] = set()
        tasks = [asyncio.create_task(ws.send_text(payload)) for ws in recipients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for ws, result in zip(recipients, results):
            if isinstance(result, Exception):
                stale.add(ws)

        for ws in stale:
            await self.disconnect(ws)

    async def broadcast_except(self, message: Dict[str, Any], exclude_websocket: WebSocket) -> None:
        """Envia mensagem para todos exceto o remetente."""
        async with self._lock:
            recipients = [ws for ws in self._connections if ws != exclude_websocket]

        if not recipients:
            return

        payload = self._serialize(message)
        if payload is None:
            return

        stale: Set[WebSocket] = set()
        tasks = [asyncio.create_task(ws.send_text(payload)) for ws in recipients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for ws, result in zip(recipients, results):
            if isinstance(result, Exception):
                stale.add(ws)

        for ws in stale:
            await self.disconnect(ws)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_users_list(self) -> list:
        """Retorna lista de usuários online (deduplicated por user_id)."""
        return [
            {
                "userId": user_id,
                "username": info["username"],
                "connectedAt": info["connected_at"],
            }
            for user_id, info in self._user_info.items()
        ]

    @staticmethod
    def _serialize(message: Dict[str, Any]) -> Optional[str]:
        try:
            return orjson.dumps(message, default=str).decode("utf-8")
        except Exception as e:
            print(f"[Chat] Erro ao serializar: {e}")
            return None

    @staticmethod
    async def _send(websocket: WebSocket, message: Dict[str, Any]) -> None:
        try:
            payload = orjson.dumps(message, default=str).decode("utf-8")
            await websocket.send_text(payload)
        except Exception as e:
            if __debug__:
                print(f"[Chat] Erro ao enviar para cliente: {e}")

    def get_connection_count(self) -> int:
        return len(self._connections)

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self._check_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if __debug__:
                    print(f"[Chat] Heartbeat erro: {e}")

    async def _check_connections(self) -> None:
        async with self._lock:
            to_check = list(self._connections)

        dead: Set[WebSocket] = set()
        for ws in to_check:
            try:
                await ws.send_text('{"type":"ping"}')
            except Exception:
                dead.add(ws)

        for ws in dead:
            await self.disconnect(ws)

        if dead and __debug__:
            print(f"[Chat] Removidas {len(dead)} conexões mortas")


chat_notifier = ChatNotifier()
