from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession
from collections import Counter

from pedidos.schema import Pedido, Status
from pedidos.service import json_string_to_items
from materiais.stats_service import get_material_stats
from safira.schemas import SafiraResponse
from safira.models import SafiraLog
from safira.intents import detect_intent

class SafiraService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ask(self, question: str, usuario_id: Optional[int] = None) -> SafiraResponse:
        intent = detect_intent(question)
        recognized = True
        answer = ""
        meta = {}

        if intent == "pedidos_hoje":
            answer = await self._get_pedidos_hoje()
        elif intent == "pedidos_em_producao":
            answer = await self._get_pedidos_em_producao()
        elif intent == "pedidos_atrasados":
            answer = await self._get_pedidos_atrasados()
        elif intent == "tipo_pedido_mais_feito":
            answer = await self._get_tipo_pedido_mais_feito()
        elif intent == "material_mais_usado":
            answer = await self._get_material_mais_usado()
        elif intent == "vendedor_mais_produtivo":
            answer = await self._get_vendedor_mais_produtivo()
        elif intent == "cliente_mais_pedidos":
            answer = await self._get_cliente_mais_pedidos()
        elif intent == "tempo_medio_producao":
            answer = await self._get_tempo_medio_producao()
        elif intent == "pedidos_concluidos_hoje":
            answer = await self._get_pedidos_concluidos_hoje()
        elif intent == "etapa_producao_com_mais_pedidos":
            answer = await self._get_etapa_producao_com_mais_pedidos()
        else:
            recognized = False
            answer = (
                "Ainda não tenho dados suficientes para responder isso.\n\n"
                "Posso ajudar com perguntas sobre:\n"
                "• pedidos\n"
                "• materiais\n"
                "• vendedores\n"
                "• produção."
            )

        # Log da pergunta
        log = SafiraLog(
            pergunta=question,
            intent_detectada=intent,
            reconhecida=recognized,
            usuario_id=usuario_id
        )
        self.session.add(log)
        await self.session.commit()

        return SafiraResponse(
            recognized=recognized,
            intent=intent,
            answer=answer,
            meta=meta
        )

    async def _get_pedidos_hoje(self) -> str:
        hoje_str = date.today().isoformat()
        query = select(func.count(Pedido.id)).where(Pedido.data_entrada == hoje_str)
        result = await self.session.execute(query)
        total = result.scalar()
        
        if total == 0:
            return "Hoje ainda não foram registrados pedidos."
        
        return f"Pedidos feitos hoje\n\n{total} pedidos registrados"

    async def _get_pedidos_em_producao(self) -> str:
        query = select(func.count(Pedido.id)).where(Pedido.status == Status.EM_PRODUCAO)
        result = await self.session.execute(query)
        total = result.scalar()
        
        if total == 0:
            return "No momento não há pedidos em produção."
        
        return f"Pedidos em produção\n\n{total} pedidos ativos agora"

    async def _get_pedidos_atrasados(self) -> str:
        hoje_str = date.today().isoformat()
        query = select(func.count(Pedido.id)).where(
            and_(
                Pedido.data_entrega < hoje_str,
                Pedido.status != Status.PRONTO,
                Pedido.status != Status.ENTREGUE,
                Pedido.status != Status.CANCELADO
            )
        )
        result = await self.session.execute(query)
        total = result.scalar()
        
        if total == 0:
            return "Não há pedidos atrasados no momento."
        
        return f"Pedidos atrasados\n\n{total} pedidos fora do prazo"

    async def _get_tipo_pedido_mais_feito(self) -> str:
        query = select(Pedido).where(Pedido.status != Status.CANCELADO)
        result = await self.session.execute(query)
        pedidos = result.scalars().all()

        tipos = []
        for p in pedidos:
            items = json_string_to_items(p.items or "[]")
            for item in items:
                if item.tipo_producao:
                    tipos.append(item.tipo_producao.capitalize())

        if not tipos:
            return "Ainda não há registros de tipos de produção no sistema."

        count = Counter(tipos)
        mais_comum = count.most_common(1)[0]
        
        return f"Tipo de pedido mais feito\n\n{mais_comum[0]}\n{mais_comum[1]} produções registradas"

    async def _get_material_mais_usado(self) -> str:
        stats = await get_material_stats(self.session)
        if stats.kpis.material_mais_usado:
            return f"Material mais usado\n\n{stats.kpis.material_mais_usado}\n{stats.kpis.total_area_m2} m² consumidos"
        return "Ainda não há dados de consumo de materiais registrados."

    async def _get_vendedor_mais_produtivo(self) -> str:
        hoje_str = date.today().isoformat()
        query = select(Pedido).where(Pedido.data_entrada == hoje_str)
        result = await self.session.execute(query)
        pedidos = result.scalars().all()

        if not pedidos:
            return "Nenhum pedido foi criado hoje até agora."

        vendedores = []
        for p in pedidos:
            items = json_string_to_items(p.items or "[]")
            for item in items:
                if item.vendedor:
                    vendedores.append(item.vendedor)
        
        if not vendedores:
            return "Os pedidos de hoje ainda não possuem vendedores vinculados."

        mais_produtivo = Counter(vendedores).most_common(1)[0]
        return f"Vendedor recordista hoje\n\n{mais_produtivo[0]}\n{mais_produtivo[1]} pedidos criados"

    async def _get_cliente_mais_pedidos(self) -> str:
        inicio_mes = date.today().replace(day=1).isoformat()
        query = select(Pedido.cliente, func.count(Pedido.id)).where(
            Pedido.data_entrada >= inicio_mes
        ).group_by(Pedido.cliente).order_by(func.count(Pedido.id).desc()).limit(1)
        
        result = await self.session.execute(query)
        res = result.first()

        if not res:
            return "Ainda não há pedidos registrados este mês."

        return f"Cliente destaque do mês\n\n{res[0]}\n{res[1]} pedidos realizados"

    async def _get_tempo_medio_producao(self) -> str:
        query = select(Pedido).where(
            and_(
                Pedido.status.in_([Status.PRONTO, Status.ENTREGUE]),
                Pedido.data_criacao != None,
                Pedido.ultima_atualizacao != None
            )
        )
        result = await self.session.execute(query)
        pedidos = result.scalars().all()

        if not pedidos:
            return "Ainda não há pedidos finalizados suficientes para calcular o tempo médio."

        tempos = [(p.ultima_atualizacao - p.data_criacao).total_seconds() for p in pedidos]
        avg_h = (sum(tempos) / len(tempos)) / 3600

        return f"Tempo médio de produção\n\n{avg_h:.1f} horas"

    async def _get_pedidos_concluidos_hoje(self) -> str:
        hoje = date.today()
        query = select(Pedido).where(
            and_(
                Pedido.status.sa_column.in_(['pronto', 'entregue']), # Usando string literal pois Status enum às vezes gera erro em query direta de data
                func.date(Pedido.ultima_atualizacao) == hoje
            )
        )
        # Note: StatusType no schema ajuda, mas aqui a query precisa ser precisa.
        # Vamos buscar todos os pedidos prontos/entregues e filtrar por data na aplicação se o SQL for complexo.
        result = await self.session.execute(select(Pedido).where(Pedido.status.in_([Status.PRONTO, Status.ENTREGUE])))
        pedidos = result.scalars().all()
        
        total = len([p for p in pedidos if p.ultima_atualizacao and p.ultima_atualizacao.date() == hoje])

        if total == 0:
            return "Ainda não tivemos pedidos concluídos hoje."

        return f"Pedidos concluídos hoje\n\n{total} pedidos prontos"

    async def _get_etapa_producao_com_mais_pedidos(self) -> str:
        query = select(Pedido.status, func.count(Pedido.id)).where(
            and_(
                Pedido.status != Status.PRONTO,
                Pedido.status != Status.ENTREGUE,
                Pedido.status != Status.CANCELADO
            )
        ).group_by(Pedido.status).order_by(func.count(Pedido.id).desc()).limit(1)

        result = await self.session.execute(query)
        res = result.first()

        if not res:
            return "No momento não há pedidos em produção."

        etapa = res[0].replace('_', ' ').capitalize()
        return f"Etapa com maior demanda\n\n{etapa}\n{res[1]} pedidos aguardando"
