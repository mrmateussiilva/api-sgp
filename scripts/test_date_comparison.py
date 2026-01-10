#!/usr/bin/env python3
"""
Teste rápido para verificar se a comparação de strings funciona para filtrar datas.
"""
from datetime import datetime, timedelta

# Simular datas que podem estar no banco
test_dates = [
    "2026-01-05",
    "2026-01-05T10:00:00",
    "2026-01-06",
    "2026-01-06T10:00:00",
    "2026-01-06T23:59:59",
    "2026-01-07",
    "2026-01-07T10:00:00",
]

data_inicio = "2026-01-06"
data_fim = "2026-01-06"

# Testar comparação direta
print("Teste 1: Comparação direta >= data_inicio")
print("-" * 60)
for date_str in test_dates:
    result = date_str >= data_inicio
    print(f"  '{date_str}' >= '{data_inicio}': {result}")

# Testar comparação com próximo dia
fim_date = datetime.strptime(data_fim, "%Y-%m-%d")
fim_plus_one = (fim_date + timedelta(days=1)).strftime("%Y-%m-%d")

print(f"\nTeste 2: Comparação < (data_fim + 1 dia) = < '{fim_plus_one}'")
print("-" * 60)
for date_str in test_dates:
    result = date_str < fim_plus_one
    print(f"  '{date_str}' < '{fim_plus_one}': {result}")

# Testar filtro combinado
print(f"\nTeste 3: Filtro combinado (>= '{data_inicio}' AND < '{fim_plus_one}')")
print("-" * 60)
filtered = []
for date_str in test_dates:
    if date_str >= data_inicio and date_str < fim_plus_one:
        filtered.append(date_str)
        print(f"  ✅ '{date_str}' passa no filtro")
    else:
        print(f"  ❌ '{date_str}' não passa no filtro")

print(f"\nResultado: {len(filtered)} datas passaram no filtro do dia 06")
print(f"Esperado: Datas do dia 06 (2026-01-06, 2026-01-06T...)")
print(f"✅ {'CORRETO' if len([d for d in filtered if d.startswith('2026-01-06')]) == len([d for d in test_dates if d.startswith('2026-01-06')]) else 'INCORRETO'}")

