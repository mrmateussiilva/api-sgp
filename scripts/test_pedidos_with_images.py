#!/usr/bin/env python3
"""
Script de teste para inserção de pedidos com quantidades aleatórias de itens.
Cada item usa a mesma imagem padrão fornecida.

Uso:
    python test_pedidos_with_images.py --api-url http://localhost:8000 --username admin --password senha --image-path imagem.jpg --num-pedidos 10
"""

import argparse
import random
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


def login(api_url: str, username: str, password: str) -> str:
    """Faz login na API e retorna o token de autenticação."""
    url = f"{api_url}/auth/login"
    response = requests.post(url, json={"username": username, "password": password})
    response.raise_for_status()
    data = response.json()
    if not data.get("success"):
        raise Exception(f"Login falhou: {data.get('message', 'Erro desconhecido')}")
    token = data.get("session_token")
    if not token:
        raise Exception("Token não retornado no login")
    print(f"✅ Login realizado com sucesso: {data.get('username')}")
    return token


def upload_image(api_url: str, token: str, image_path: str) -> str:
    """Faz upload da imagem e retorna a referência do servidor."""
    url = f"{api_url}/pedidos/order-items/upload-image"
    
    with open(image_path, 'rb') as f:
        files = {'image': (Path(image_path).name, f, 'image/jpeg')}
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(url, files=files, headers=headers)
        response.raise_for_status()
        data = response.json()
        
    server_reference = data.get('server_reference') or data.get('image_reference') or data.get('path')
    if not server_reference:
        raise Exception(f"Referência de imagem não retornada: {data}")
    
    print(f"✅ Imagem enviada: {server_reference}")
    return server_reference


def create_order(api_url: str, token: str, order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Cria um pedido na API."""
    url = f"{api_url}/pedidos/"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, json=order_data, headers=headers)
    response.raise_for_status()
    return response.json()


def generate_random_items(num_items: int, image_reference: str) -> List[Dict[str, Any]]:
    """Gera itens aleatórios para um pedido."""
    tipos_producao = ['painel', 'lona', 'totem', 'adesivo']
    vendedores = ['João Silva', 'Maria Santos', 'Pedro Costa', 'Ana Lima']
    designers = ['Carlos Design', 'Julia Art', 'Roberto Visual', 'Fernanda Criativa']
    tecidos = ['Tactel', 'Lona Fosca', 'Lona Frontlight', 'Tecido Display']
    
    items = []
    for i in range(num_items):
        tipo = random.choice(tipos_producao)
        largura = round(random.uniform(1.0, 5.0), 2)
        altura = round(random.uniform(1.0, 3.0), 2)
        metro_quadrado = round(largura * altura, 2)
        valor_unitario = round(random.uniform(50.0, 500.0), 2)
        
        item = {
            "tipo_producao": tipo,
            "descricao": f"{tipo.capitalize()} {largura}x{altura}m",
            "largura": str(largura),
            "altura": str(altura),
            "metro_quadrado": str(metro_quadrado),
            "vendedor": random.choice(vendedores),
            "designer": random.choice(designers),
            "tecido": random.choice(tecidos),
            "valor_unitario": str(valor_unitario),
            "imagem": image_reference,  # Usar a mesma imagem para todos os itens
            "legenda_imagem": f"Imagem padrão - Item {i+1}",
            "observacao": f"Item de teste {i+1}",
        }
        
        # Adicionar campos específicos por tipo
        if tipo == 'painel':
            item.update({
                "quantidade_paineis": str(random.randint(1, 5)),
                "emenda": random.choice(["sem-emenda", "vertical", "horizontal"]),
            })
        elif tipo == 'lona':
            item.update({
                "quantidade_lona": str(random.randint(1, 3)),
                "acabamento_lona": random.choice(["refilar", "nao_refilar"]),
            })
        elif tipo == 'totem':
            item.update({
                "quantidade_totem": str(random.randint(1, 2)),
                "acabamento_totem": random.choice(["com_pe", "sem_pe"]),
            })
        elif tipo == 'adesivo':
            item.update({
                "quantidade_adesivo": str(random.randint(1, 4)),
                "tipo_adesivo": random.choice(["adesivo", "vinil"]),
            })
        
        items.append(item)
    
    return items


def generate_order_data(order_num: int, image_reference: str) -> Dict[str, Any]:
    """Gera dados de um pedido aleatório."""
    num_items = random.randint(1, 5)  # Entre 1 e 5 itens por pedido
    
    clientes = [
        "Cliente Teste A", "Cliente Teste B", "Cliente Teste C",
        "Cliente Teste D", "Cliente Teste E"
    ]
    cidades = [
        "São Paulo", "Rio de Janeiro", "Belo Horizonte",
        "Curitiba", "Porto Alegre"
    ]
    estados = ["SP", "RJ", "MG", "PR", "RS"]
    
    cliente_idx = random.randint(0, len(clientes) - 1)
    data_entrada = datetime.now().date().isoformat()
    data_entrega = (datetime.now() + timedelta(days=random.randint(7, 30))).date().isoformat()
    
    items = generate_random_items(num_items, image_reference)
    
    # Calcular valores
    valor_itens = sum(float(item["valor_unitario"]) for item in items)
    valor_frete = round(random.uniform(10.0, 50.0), 2)
    valor_total = valor_itens + valor_frete
    
    return {
        "cliente": f"{clientes[cliente_idx]} - Pedido {order_num}",
        "telefone_cliente": f"(11) 9{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
        "cidade_cliente": cidades[cliente_idx],
        "estado_cliente": estados[cliente_idx],
        "data_entrada": data_entrada,
        "data_entrega": data_entrega,
        "status": "pendente",
        "prioridade": random.choice(["NORMAL", "ALTA"]),
        "valor_total": str(round(valor_total, 2)),
        "valor_frete": str(round(valor_frete, 2)),
        "forma_envio": random.choice(["Sedex", "PAC", "Motoboy", "Retirada"]),
        "observacao": f"Pedido de teste #{order_num} com {num_items} item(s)",
        "items": items
    }


def main():
    parser = argparse.ArgumentParser(description='Script de teste para inserção de pedidos com imagens')
    parser.add_argument('--api-url', default='http://localhost:8000', help='URL da API')
    parser.add_argument('--username', required=True, help='Usuário para login')
    parser.add_argument('--password', required=True, help='Senha para login')
    parser.add_argument('--image-path', required=True, help='Caminho da imagem padrão')
    parser.add_argument('--num-pedidos', type=int, default=10, help='Número de pedidos a criar (padrão: 10)')
    
    args = parser.parse_args()
    
    # Validar imagem
    image_path = Path(args.image_path)
    if not image_path.exists():
        print(f"❌ Erro: Imagem não encontrada: {image_path}")
        return 1
    
    print(f"🚀 Iniciando teste de inserção de pedidos...")
    print(f"   API URL: {args.api_url}")
    print(f"   Imagem: {image_path}")
    print(f"   Número de pedidos: {args.num_pedidos}")
    print()
    
    try:
        # 1. Login
        token = login(args.api_url, args.username, args.password)
        
        # 2. Upload da imagem padrão
        image_reference = upload_image(args.api_url, token, str(image_path))
        print()
        
        # 3. Criar pedidos
        print(f"📦 Criando {args.num_pedidos} pedidos...")
        success_count = 0
        error_count = 0
        
        for i in range(1, args.num_pedidos + 1):
            try:
                order_data = generate_order_data(i, image_reference)
                result = create_order(args.api_url, token, order_data)
                success_count += 1
                print(f"  ✅ Pedido {i}/{args.num_pedidos} criado: ID {result.get('id')}, {len(order_data['items'])} item(s)")
            except Exception as e:
                error_count += 1
                print(f"  ❌ Erro ao criar pedido {i}: {e}")
        
        print()
        print(f"✅ Teste concluído!")
        print(f"   Sucessos: {success_count}/{args.num_pedidos}")
        print(f"   Erros: {error_count}/{args.num_pedidos}")
        
        return 0 if error_count == 0 else 1
        
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        return 1


if __name__ == '__main__':
    exit(main())

