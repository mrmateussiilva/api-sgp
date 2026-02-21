import httpx
import logging
from typing import Any, Dict
from datetime import datetime
from config import settings
from pedidos.schema import PedidoResponse

logger = logging.getLogger(__name__)

class VpsSyncService:
    @staticmethod
    async def sync_pedido(pedido: PedidoResponse) -> None:
        """
        Envia os dados de um pedido para a VPS de forma assíncrona.
        """
        logger.info("[VPS-SYNC] Iniciando sync_pedido para pedido_id=%s", pedido.id)
        if settings.ENVIRONMENT == "test":
            # Não sincronizar durante os testes automatizados
            return

        if not settings.VPS_SYNC_URL:
            logger.warning("[VPS-SYNC] URL de sincronização da VPS não configurada.")
            return

        # Tentar converter valor_total para float para evitar erros de tipo na VPS
        try:
            valor_f = float(pedido.valor_total) if pedido.valor_total else 0.0
        except (ValueError, TypeError):
            valor_f = 0.0

        # Formatar data
        if isinstance(pedido.ultima_atualizacao, datetime):
            updated_at = pedido.ultima_atualizacao.isoformat()
        else:
            updated_at = str(pedido.ultima_atualizacao)
        
        # Garantir sufixo 'Z' se não houver timezone (assumindo UTC)
        if 'T' in updated_at and '+' not in updated_at and updated_at.count('-') <= 2:
            if not updated_at.endswith('Z'):
                updated_at += 'Z'

        # Payload compatível com o modelo Pedido da API mobile (pwa_pedidos)
        pedido_data = {
            "pedido_id": pedido.id,
            "numero": pedido.numero,
            "cliente": pedido.cliente or "",
            "data_entrada": getattr(pedido, "data_entrada", None) or "",
            "data_entrega": getattr(pedido, "data_entrega", None) or "",
            "status": pedido.status.value if hasattr(pedido.status, 'value') else str(pedido.status),
            "valor_total": valor_f,
            "observacao": getattr(pedido, "observacao", None) or "",
        }
        payload = [pedido_data]

        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    settings.VPS_SYNC_URL,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code >= 400:
                    logger.error(
                        "[VPS-SYNC] Falha ao sincronizar pedido %s com a VPS. Status: %s, Resposta: %s, Payload: %s",
                        pedido.id,
                        response.status_code,
                        response.text,
                        payload
                    )
                else:
                    logger.info("[VPS-SYNC] Pedido %s sincronizado com sucesso com a VPS. Payload: %s", pedido.id, payload)
                    
        except httpx.TimeoutException:
            logger.error("[VPS-SYNC] Timeout ao sincronizar pedido %s com a VPS (máx 3s).", pedido.id)
        except Exception as e:
            logger.error("[VPS-SYNC] Erro inesperado ao sincronizar pedido %s com a VPS: %s", pedido.id, str(e))

    @staticmethod
    async def sync_deletion(pedido: PedidoResponse) -> None:
        """
        Informa a VPS que um pedido foi deletado.
        """
        logger.info("[VPS-SYNC] Iniciando sync_deletion para pedido_id=%s", pedido.id)
        if settings.ENVIRONMENT == "test":
            return

        if not settings.VPS_SYNC_URL:
            return

        # Tentar converter valor_total para float
        try:
            valor_f = float(pedido.valor_total) if pedido.valor_total else 0.0
        except (ValueError, TypeError):
            valor_f = 0.0

        # Formatar data
        if isinstance(pedido.ultima_atualizacao, datetime):
            updated_at = pedido.ultima_atualizacao.isoformat()
        else:
            updated_at = str(pedido.ultima_atualizacao)
        
        if 'T' in updated_at and '+' not in updated_at and updated_at.count('-') <= 2:
            if not updated_at.endswith('Z'):
                updated_at += 'Z'

        # Para deleção, enviamos objeto compatível com o modelo Pedido da API mobile
        # (a API mobile pode tratar deleção via outro mecanismo no futuro)
        pedido_data = {
            "pedido_id": pedido.id,
            "numero": pedido.numero,
            "cliente": pedido.cliente or "",
            "data_entrada": getattr(pedido, "data_entrada", None) or "",
            "data_entrega": getattr(pedido, "data_entrega", None) or "",
            "status": pedido.status.value if hasattr(pedido.status, 'value') else str(pedido.status),
            "valor_total": valor_f,
            "observacao": getattr(pedido, "observacao", None) or "",
        }
        payload = [pedido_data]
        
        headers = {"Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.post(
                    settings.VPS_SYNC_URL,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code >= 400:
                    logger.error(
                        "[VPS-SYNC] Falha ao sincronizar deleção do pedido %s. Status: %s, Resposta: %s, Payload: %s",
                        pedido.id,
                        response.status_code,
                        response.text,
                        payload
                    )
                else:
                    logger.info("[VPS-SYNC] Deleção do pedido %s sincronizada com a VPS. Payload: %s", pedido.id, payload)
                    
        except Exception as e:
            logger.error("[VPS-SYNC] Erro ao sincronizar deleção do pedido %s: %s", pedido.id, str(e))

vps_sync_service = VpsSyncService()
