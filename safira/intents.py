import re
import unicodedata

def normalize_text(text: str) -> str:
    # Converter para minúsculas
    text = text.lower()
    # Remover acentos
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    # Remover pontuações básicas
    text = re.sub(r'[?!\.,;]', '', text)
    return text.strip()

INTENTS_KEYWORDS = {
    "pedidos_hoje": [
        "pedidos hoje", "quantos pedidos hoje", "quantos pedidos foram feitos hoje", "registrados hoje", "entraram hoje"
    ],
    "pedidos_em_producao": [
        "em producao", "fazendo agora", "sendo produzidos", "na fabrica", "na producao"
    ],
    "pedidos_atrasados": [
        "pedidos atrasados", "o que esta atrasado", "atraso", "pedidos fora do prazo"
    ],
    "tipo_pedido_mais_feito": [
        "tipo de pedido mais", "tipo mais feito", "mais vendido", "categoria mais"
    ],
    "material_mais_usado": [
        "material mais usado", "material e mais usado", "tecido mais usado", "mais consumido", "mais utilizado"
    ],
    "vendedor_mais_produtivo": [
        "vendedor criou mais", "vendedor produziu mais", "vendedor mais produtivo hoje", "vendedor hoje"
    ],
    "cliente_mais_pedidos": [
        "cliente mais pedidos", "cliente fiel", "quem mais comprou este mes", "principal cliente"
    ],
    "tempo_medio_producao": [
        "tempo medio de producao", "quanto tempo demora a producao", "prazo medio"
    ],
    "pedidos_concluidos_hoje": [
        "concluidos hoje", "finalizados hoje", "prontos hoje", "entregues hoje"
    ],
    "etapa_producao_com_mais_pedidos": [
        "etapa com mais pedidos", "qual etapa da producao tem mais pedidos", "gargalo", "onde estao a maioria dos pedidos", "etapa da producao"
    ]
}

def detect_intent(question: str) -> str:
    normalized_question = normalize_text(question)
    
    for intent, keywords in INTENTS_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_question:
                return intent
                
    return "unknown"
