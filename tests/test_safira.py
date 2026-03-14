from safira.intents import detect_intent, normalize_text

def test_intent_detection():
    # Test normalization
    assert normalize_text("Qual o Tempo Médio?!") == "qual o tempo medio"
    
    # Test specific intents
    assert detect_intent("Qual o tempo médio de produção?") == "tempo_medio_producao"
    assert detect_intent("Qual o tipo de pedido mais feito?") == "tipo_pedido_mais_feito"
    assert detect_intent("Qual vendedor produziu mais hoje?") == "vendedor_mais_produtivo"
    assert detect_intent("Qual material é mais usado?") == "material_mais_usado"
    assert detect_intent("Quantos pedidos foram feitos hoje?") == "pedidos_hoje"
    assert detect_intent("Qual etapa da produção tem mais pedidos?") == "etapa_producao_com_mais_pedidos"
    assert detect_intent("Qual a cor do céu?") == "unknown"
