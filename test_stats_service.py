import asyncio
import os
import sys

# Add current dir to python_path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from pprint import pprint

from database.database import async_session_maker
from materiais.stats_service import get_material_stats, get_material_evolution

async def run_test():
    async with async_session_maker() as session:
        # Pega a data de hoje e 30 dias atras
        hoje = datetime.now()
        trinta_dias = hoje - timedelta(days=30)
        
        data_inicio = trinta_dias.strftime("%Y-%m-%d")
        data_fim = hoje.strftime("%Y-%m-%d")
        
        print(f"Buscando de {data_inicio} ate {data_fim}")
        
        stats = await get_material_stats(session, data_inicio=data_inicio, data_fim=data_fim)
        evol = await get_material_evolution(session, data_inicio=data_inicio, data_fim=data_fim)
        
        print("\n--- STATS ---")
        print("KPIs:", stats.kpis)
        print("Ranking (Top 3):", stats.ranking_materiais[:3])
        
        print("\n--- EVOLUTION ---")
        print("Top 3:", evol.top_3_nomes)
        print("Evolucao (Top 3 dias):", evol.evolucao[:3])
        
        # Se veio vazio, vamos testar sem filtro de data
        if not stats.ranking_materiais:
            print("\nVazio com as datas atuais. Buscando SEM filtros de data...")
            stats_all = await get_material_stats(session)
            print("KPIs (Sem data):", stats_all.kpis)
            print("Ranking (Sem data, Top 3):", stats_all.ranking_materiais[:3])

if __name__ == "__main__":
    asyncio.run(run_test())
