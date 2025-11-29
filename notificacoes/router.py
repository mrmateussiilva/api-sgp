from fastapi import APIRouter
from datetime import datetime
from pedidos.router import ULTIMO_PEDIDO_ID

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("/ultimos")
async def ultimas_notificacoes():
    """
    Retorna o último ID de pedido criado e timestamp atual.
    Usado para long polling de notificações de novos pedidos.
    """
    return {
        "ultimo_id": ULTIMO_PEDIDO_ID,
        "timestamp": datetime.now().isoformat()
    }

