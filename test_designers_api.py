import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000/api/v1"

def test_designers_api():
    # 1. Buscar designers para pegar um nome válido
    try:
        resp = requests.get(f"{BASE_URL}/designers/")
        designers = resp.json()
        if not designers:
            print("Nenhum designer cadastrado.")
            return
        
        designer_nome = designers[0]['nome']
        print(f"Testando com designer: {designer_nome}")
        
    except Exception as e:
        print(f"Erro ao conectar na API: {e}")
        return

    # 2. Testar busca sem filtros
    resp = requests.get(f"{BASE_URL}/designers/{designer_nome}/itens")
    items = resp.json()
    print(f"Total de itens sem filtro: {len(items)}")

    # 3. Testar busca com filtro de data (últimos 7 dias)
    today = datetime.now()
    seven_days_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')
    
    resp = requests.get(f"{BASE_URL}/designers/{designer_nome}/itens", params={
        "start_date": seven_days_ago,
        "end_date": today_str
    })
    items_filtered = resp.json()
    print(f"Total de itens (últimos 7 dias): {len(items_filtered)}")

    # 4. Testar paginação (limit=2)
    resp = requests.get(f"{BASE_URL}/designers/{designer_nome}/itens", params={
        "limit": 2
    })
    items_paginated = resp.json()
    print(f"Itens paginados (limit=2): {len(items_paginated)}")
    if len(items_paginated) > 0:
        print(f"Primeiro item ID: {items_paginated[0]['item_id']}")

if __name__ == "__main__":
    test_designers_api()
