import asyncio
from typing import Any, Dict, Set, Optional
from collections import defaultdict

import orjson
from fastapi import WebSocket

class OrdersNotifier:
    def __init__(self) -> None:
        # Rastrear conexões por user_id (múltiplas conexões por usuário são permitidas)
        self._connections: Set[WebSocket] = set()
        self._connections_by_user: Dict[int, Set[WebSocket]] = defaultdict(set)
        self._user_by_websocket: Dict[WebSocket, int] = {}
        self._lock = asyncio.Lock()
        # Heartbeat para detectar conexões mortas
        self._heartbeat_interval = 30  # segundos
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        """
        Conecta um WebSocket.

        IMPORTANTE: não fechamos mais conexões antigas do mesmo usuário.
        Isso permite múltiplos computadores/abas usando o mesmo login receberem
        eventos em tempo real (broadcast) simultaneamente.
        """
        async with self._lock:
            
            # Adicionar nova conexão
            self._connections.add(websocket)
            self._connections_by_user[user_id].add(websocket)
            self._user_by_websocket[websocket] = user_id
            
            if __debug__:
                print(f"[WebSocket] Cliente conectado (user_id={user_id}, total={len(self._connections)}, por_usuario={len(self._connections_by_user[user_id])})")
            
            # Iniciar heartbeat se ainda não estiver rodando
            if self._heartbeat_task is None or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, websocket: WebSocket) -> None:
        """Desconecta um WebSocket e limpa todas as referências."""
        async with self._lock:
            if websocket in self._connections:
                user_id = self._user_by_websocket.pop(websocket, None)
                if user_id:
                    self._connections_by_user[user_id].discard(websocket)
                    if not self._connections_by_user[user_id]:
                        del self._connections_by_user[user_id]
                
                self._connections.remove(websocket)
                if __debug__:
                    print(f"[WebSocket] Cliente desconectado (user_id={user_id}, total: {len(self._connections)})")

    async def _heartbeat_loop(self) -> None:
        """Loop de heartbeat para detectar e remover conexões mortas."""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                await self._check_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                if __debug__:
                    print(f"[WebSocket] Erro no heartbeat loop: {e}")

    async def _check_connections(self) -> None:
        """Verifica conexões ativas e remove as mortas."""
        async with self._lock:
            dead_connections = set()
            connections_to_check = list(self._connections)
        
        for websocket in connections_to_check:
            try:
                # Tentar enviar ping para verificar se a conexão está viva
                await websocket.send_text('{"type":"ping"}')
            except Exception:
                dead_connections.add(websocket)
        
        if dead_connections:
            for ws in dead_connections:
                await self.disconnect(ws)
            if __debug__:
                print(f"[WebSocket] Removidas {len(dead_connections)} conexões mortas pelo heartbeat")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        async with self._lock:
            recipients = list(self._connections)

        if not recipients:
            # Log apenas em desenvolvimento para não poluir logs de produção
            if __debug__:
                print(f"[WebSocket] Nenhum cliente conectado para broadcast: {message.get('type', 'unknown')}")
            return

        try:
            payload = orjson.dumps(message, default=str).decode("utf-8")
        except Exception as e:
            print(f"[WebSocket] Erro ao serializar mensagem: {e}")
            return

        stale_connections: Set[WebSocket] = set()
        successful_sends = 0

        send_tasks = [
            asyncio.create_task(websocket.send_text(payload))
            for websocket in recipients
        ]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        for websocket, result in zip(recipients, results):
            if isinstance(result, Exception):
                stale_connections.add(websocket)
                if __debug__:
                    print(f"[WebSocket] Erro ao enviar para cliente: {type(result).__name__}: {result}")
            else:
                successful_sends += 1

        if __debug__:
            event_type = message.get('type', 'unknown')
            order_id = message.get('order_id') or (message.get('order', {}).get('id') if isinstance(message.get('order'), dict) else None)
            print(f"[WebSocket] Broadcast '{event_type}' (pedido_id={order_id}): {successful_sends}/{len(recipients)} clientes notificados")

        if stale_connections:
            for websocket in stale_connections:
                await self.disconnect(websocket)

    async def broadcast_except(self, message: Dict[str, Any], exclude_websocket: WebSocket) -> None:
        """Envia mensagem para todos os clientes EXCETO o especificado (o remetente)."""
        async with self._lock:
            recipients = [ws for ws in self._connections if ws != exclude_websocket]

        if not recipients:
            if __debug__:
                print(f"[WebSocket] Nenhum outro cliente para broadcast: {message.get('type', 'unknown')}")
            return

        try:
            payload = orjson.dumps(message, default=str).decode("utf-8")
        except Exception as e:
            print(f"[WebSocket] Erro ao serializar mensagem: {e}")
            return

        stale_connections: Set[WebSocket] = set()
        successful_sends = 0

        send_tasks = [
            asyncio.create_task(websocket.send_text(payload))
            for websocket in recipients
        ]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        for websocket, result in zip(recipients, results):
            if isinstance(result, Exception):
                stale_connections.add(websocket)
                if __debug__:
                    print(f"[WebSocket] Erro ao enviar para cliente: {type(result).__name__}: {result}")
            else:
                successful_sends += 1

        if __debug__:
            event_type = message.get('type', 'unknown')
            order_id = message.get('order_id') or (message.get('order', {}).get('id') if isinstance(message.get('order'), dict) else None)
            print(f"[WebSocket] Broadcast '{event_type}' (exceto sender, pedido_id={order_id}): {successful_sends}/{len(recipients)} clientes notificados")

        if stale_connections:
            for websocket in stale_connections:
                await self.disconnect(websocket)

    def get_connection_count(self) -> int:
        """Retorna o número total de conexões ativas."""
        return len(self._connections)
    
    def get_connections_by_user(self) -> Dict[int, int]:
        """Retorna o número de conexões por usuário."""
        return {user_id: len(connections) for user_id, connections in self._connections_by_user.items()}


orders_notifier = OrdersNotifier()


def schedule_broadcast(message: Dict[str, Any]) -> None:
    """
    Agenda um broadcast para todos os clientes WebSocket conectados.
    Esta função é thread-safe e pode ser chamada de qualquer contexto.
    """
    if __debug__:
        print(f"[schedule_broadcast] Recebido pedido de broadcast: type={message.get('type')}, order_id={message.get('order_id')}")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # Se não houver event loop, tentar criar um novo (raro, mas possível)
        if __debug__:
            print("[WebSocket] Nenhum event loop disponível para broadcast")
        return

    if not loop.is_running():
        if __debug__:
            print("[WebSocket] Event loop não está rodando, broadcast não será enviado")
        return

    # Criar task assíncrona para broadcast não-bloqueante
    if __debug__:
        connection_count = orders_notifier.get_connection_count()
        print(f"[schedule_broadcast] Criando task de broadcast para {connection_count} conexões")
    
    task = loop.create_task(orders_notifier.broadcast(message))
    
    # Adicionar callback de erro para evitar que erros silenciosos quebrem o sistema
    def handle_task_error(task: asyncio.Task) -> None:
        try:
            task.result()  # Isso vai levantar exceção se houver
        except Exception as e:
            print(f"[WebSocket] Erro no broadcast task: {e}")
    
    task.add_done_callback(handle_task_error)
