import asyncio
from typing import Any, Dict, Set

import orjson
from fastapi import WebSocket

class OrdersNotifier:
    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        # Conexão já foi aceita antes de chamar este método
        async with self._lock:
            self._connections.add(websocket)
            if __debug__:
                print(f"[WebSocket] Cliente conectado (total: {len(self._connections)})")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
                if __debug__:
                    print(f"[WebSocket] Cliente desconectado (total: {len(self._connections)})")

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
            async with self._lock:
                for websocket in stale_connections:
                    if websocket in self._connections:
                        self._connections.remove(websocket)
                        if __debug__:
                            print(f"[WebSocket] Cliente desconectado removido (total: {len(self._connections)})")


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
        print(f"[schedule_broadcast] Criando task de broadcast para {len(orders_notifier._connections)} conexões")
    
    task = loop.create_task(orders_notifier.broadcast(message))
    
    # Adicionar callback de erro para evitar que erros silenciosos quebrem o sistema
    def handle_task_error(task: asyncio.Task) -> None:
        try:
            task.result()  # Isso vai levantar exceção se houver
        except Exception as e:
            print(f"[WebSocket] Erro no broadcast task: {e}")
    
    task.add_done_callback(handle_task_error)
