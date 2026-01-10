#!/usr/bin/env python3
"""
Script para mesclar dados dos arquivos JSON com o banco de dados SQL.
- Importa pedidos que estão nos JSONs mas faltam no banco
- Corrige datas de entrega incorretas baseado nos JSONs
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import sys

# Caminhos
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEDIA_PEDIDOS = PROJECT_ROOT / "media" / "pedidos"
DB_PATH = PROJECT_ROOT / "db" / "banco.db"

def normalize_date(value):
    """Normaliza uma data para formato YYYY-MM-DD."""
    if not value:
        return None
    if isinstance(value, str):
        value = value.strip()
        if len(value) >= 10:
            return value[:10]  # Extrair apenas YYYY-MM-DD
    return value

def extract_full_pedido_from_json(pedido_id, json_file):
    """Extrai todos os dados de um pedido de um arquivo JSON."""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Normalizar campos de data
        data_entrada = normalize_date(data.get('data_entrada'))
        data_entrega = normalize_date(data.get('data_entrega'))
        
        # Normalizar cidade/estado
        cidade_cliente = data.get('cidade_cliente') or data.get('address') or ''
        estado_cliente = data.get('estado_cliente') or ''
        if cidade_cliente and estado_cliente:
            # Separar cidade e estado se vierem juntos (ex: "Cidade (UF)")
            if '(' in cidade_cliente and ')' in cidade_cliente:
                parts = cidade_cliente.split('(')
                if len(parts) == 2:
                    cidade_cliente = parts[0].strip()
                    estado_cliente = parts[1].replace(')', '').strip()
            # Combinar cidade e estado se necessário
            if estado_cliente:
                cidade_cliente = f"{cidade_cliente}||{estado_cliente}"
        
        # Normalizar items
        items = data.get('items', [])
        # Remover campos que não são do banco dos items
        items_clean = []
        for item in items:
            item_clean = {k: v for k, v in item.items() 
                         if k not in ['order_id', 'item_name', 'quantity', 'unit_price', 'subtotal', 
                                     'legenda_imagem', 'savedAt', 'savedBy', 'version']}
            items_clean.append(item_clean)
        
        # Converter items para JSON string
        items_json = json.dumps(items_clean, ensure_ascii=False) if items_clean else '[]'
        
        # Normalizar status - garantir valores minúsculos conforme schema
        status = data.get('status', 'pendente')
        status_lower = str(status).lower().strip()
        
        # Mapear valores comuns para os valores corretos do schema
        status_map = {
            'concluido': 'entregue',
            'concluído': 'entregue',
            'pendente': 'pendente',
            'em producao': 'em_producao',
            'em produção': 'em_producao',
            'em_producao': 'em_producao',
            'pronto': 'pronto',
            'entregue': 'entregue',
            'cancelado': 'cancelado',
        }
        
        status = status_map.get(status_lower, 'pendente')
        
        # Normalizar prioridade
        prioridade = data.get('prioridade', 'NORMAL')
        if prioridade not in ['NORMAL', 'ALTA']:
            prioridade = 'NORMAL'
        
        # Normalizar forma_envio_id
        forma_envio_id = data.get('forma_envio_id') or data.get('forma_pagamento_id') or 0
        try:
            forma_envio_id = int(forma_envio_id)
        except (ValueError, TypeError):
            forma_envio_id = 0
        
        # Normalizar valores
        valor_total = str(data.get('valor_total') or data.get('total_value') or '0.00')
        valor_frete = str(data.get('valor_frete') or '0.00')
        valor_itens = str(data.get('valor_itens') or '0.00')
        
        # Normalizar created_at e updated_at
        created_at = data.get('created_at') or data.get('data_criacao')
        updated_at = data.get('updated_at') or data.get('ultima_atualizacao') or created_at
        
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                created_at = datetime.utcnow()
        elif created_at is None:
            created_at = datetime.utcnow()
        
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            except:
                updated_at = datetime.utcnow()
        elif updated_at is None:
            updated_at = datetime.utcnow()
        
        return {
            'id': data.get('id') or pedido_id,
            'numero': data.get('numero') or f"{pedido_id:010d}",
            'data_entrada': data_entrada or datetime.utcnow().date().isoformat(),
            'data_entrega': data_entrega,
            'observacao': data.get('observacao') or '',
            'prioridade': prioridade,
            'status': status,
            'cliente': data.get('cliente') or data.get('customer_name') or '',
            'telefone_cliente': data.get('telefone_cliente') or '',
            'cidade_cliente': cidade_cliente,
            'valor_total': valor_total,
            'valor_frete': valor_frete,
            'valor_itens': valor_itens,
            'tipo_pagamento': data.get('tipo_pagamento') or '',
            'obs_pagamento': data.get('obs_pagamento') or '',
            'forma_envio': data.get('forma_envio') or '',
            'forma_envio_id': forma_envio_id,
            'financeiro': bool(data.get('financeiro', False)),
            'conferencia': bool(data.get('conferencia', False)),
            'sublimacao': bool(data.get('sublimacao', False)),
            'costura': bool(data.get('costura', False)),
            'expedicao': bool(data.get('expedicao', False)),
            'pronto': bool(data.get('pronto', False)),
            'sublimacao_maquina': data.get('sublimacao_maquina') or None,
            'sublimacao_data_impressao': normalize_date(data.get('sublimacao_data_impressao')),
            'items': items_json,
            'data_criacao': created_at,
            'ultima_atualizacao': updated_at,
        }
    except Exception as e:
        print(f"⚠️ Erro ao ler JSON {json_file}: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_all_json_pedidos():
    """Busca todos os pedidos dos arquivos JSON."""
    pedidos_json = {}
    
    print("📂 Lendo arquivos JSON em media/pedidos/...")
    
    if not MEDIA_PEDIDOS.exists():
        print(f"❌ Diretório não encontrado: {MEDIA_PEDIDOS}")
        return {}
    
    for pedido_dir in MEDIA_PEDIDOS.iterdir():
        if not pedido_dir.is_dir() or pedido_dir.name == "tmp":
            continue
            
        try:
            pedido_id = int(pedido_dir.name)
        except ValueError:
            continue
        
        # Pegar o arquivo JSON mais recente de cada pedido
        json_files = list(pedido_dir.glob("pedido-*.json"))
        if not json_files:
            continue
        
        # Ordenar por data de modificação (mais recente primeiro)
        json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        latest_json = json_files[0]
        
        pedido_data = extract_full_pedido_from_json(pedido_id, latest_json)
        if pedido_data:
            pedidos_json[pedido_id] = pedido_data
    
    print(f"✅ Encontrados {len(pedidos_json)} pedidos nos arquivos JSON\n")
    return pedidos_json

def get_database_pedidos(conn):
    """Busca todos os pedidos do banco de dados."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id, numero, data_entrada, data_entrega, observacao, prioridade, status,
            cliente, telefone_cliente, cidade_cliente, valor_total, valor_frete, valor_itens,
            tipo_pagamento, obs_pagamento, forma_envio, forma_envio_id,
            financeiro, conferencia, sublimacao, costura, expedicao, pronto,
            sublimacao_maquina, sublimacao_data_impressao, items,
            data_criacao, ultima_atualizacao
        FROM pedidos
        ORDER BY id
    """)
    
    pedidos_db = {}
    for row in cursor.fetchall():
        pedido_id = row[0]
        pedidos_db[pedido_id] = {
            'id': row[0],
            'numero': row[1],
            'data_entrada': row[2],
            'data_entrega': row[3],
            'observacao': row[4],
            'prioridade': row[5],
            'status': row[6],
            'cliente': row[7],
            'telefone_cliente': row[8],
            'cidade_cliente': row[9],
            'valor_total': row[10],
            'valor_frete': row[11],
            'valor_itens': row[12],
            'tipo_pagamento': row[13],
            'obs_pagamento': row[14],
            'forma_envio': row[15],
            'forma_envio_id': row[16],
            'financeiro': bool(row[17]) if row[17] is not None else False,
            'conferencia': bool(row[18]) if row[18] is not None else False,
            'sublimacao': bool(row[19]) if row[19] is not None else False,
            'costura': bool(row[20]) if row[20] is not None else False,
            'expedicao': bool(row[21]) if row[21] is not None else False,
            'pronto': bool(row[22]) if row[22] is not None else False,
            'sublimacao_maquina': row[23],
            'sublimacao_data_impressao': row[24],
            'items': row[25],
            'data_criacao': row[26],
            'ultima_atualizacao': row[27],
        }
    
    return pedidos_db

def insert_pedido(conn, pedido_data, dry_run=False):
    """Insere um pedido no banco de dados."""
    cursor = conn.cursor()
    
    # Garantir que data_entrada não seja None
    if not pedido_data.get('data_entrada'):
        pedido_data['data_entrada'] = datetime.utcnow().date().isoformat()
    
    try:
        cursor.execute("""
            INSERT INTO pedidos (
                id, numero, data_entrada, data_entrega, observacao, prioridade, status,
                cliente, telefone_cliente, cidade_cliente, valor_total, valor_frete, valor_itens,
                tipo_pagamento, obs_pagamento, forma_envio, forma_envio_id,
                financeiro, conferencia, sublimacao, costura, expedicao, pronto,
                sublimacao_maquina, sublimacao_data_impressao, items,
                data_criacao, ultima_atualizacao
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pedido_data['id'],
            pedido_data['numero'],
            pedido_data['data_entrada'],
            pedido_data.get('data_entrega'),
            pedido_data.get('observacao', ''),
            pedido_data.get('prioridade', 'NORMAL'),
            pedido_data.get('status', 'pendente'),
            pedido_data.get('cliente', ''),
            pedido_data.get('telefone_cliente', ''),
            pedido_data.get('cidade_cliente', ''),
            pedido_data.get('valor_total', '0.00'),
            pedido_data.get('valor_frete', '0.00'),
            pedido_data.get('valor_itens', '0.00'),
            pedido_data.get('tipo_pagamento', ''),
            pedido_data.get('obs_pagamento', ''),
            pedido_data.get('forma_envio', ''),
            pedido_data.get('forma_envio_id', 0),
            pedido_data.get('financeiro', False),
            pedido_data.get('conferencia', False),
            pedido_data.get('sublimacao', False),
            pedido_data.get('costura', False),
            pedido_data.get('expedicao', False),
            pedido_data.get('pronto', False),
            pedido_data.get('sublimacao_maquina'),
            pedido_data.get('sublimacao_data_impressao'),
            pedido_data.get('items', '[]'),
            pedido_data.get('data_criacao', datetime.utcnow()),
            pedido_data.get('ultima_atualizacao', datetime.utcnow()),
        ))
        
        if not dry_run:
            conn.commit()
            return True
        return True
    except sqlite3.IntegrityError as e:
        if 'UNIQUE' in str(e) or 'PRIMARY KEY' in str(e):
            print(f"  ⚠️ Pedido ID {pedido_data['id']} já existe no banco (será atualizado)")
            return False
        raise
    except Exception as e:
        print(f"  ❌ Erro ao inserir pedido ID {pedido_data['id']}: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_pedido_data_entrega(conn, pedido_id, nova_data_entrega, dry_run=False):
    """Atualiza apenas a data_entrega de um pedido."""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE pedidos 
            SET data_entrega = ?, ultima_atualizacao = ?
            WHERE id = ?
        """, (nova_data_entrega, datetime.utcnow(), pedido_id))
        
        if not dry_run:
            conn.commit()
            return True
        return True
    except Exception as e:
        print(f"  ❌ Erro ao atualizar pedido ID {pedido_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def merge_json_with_database(dry_run=True):
    """Mescla dados dos JSONs com o banco de dados."""
    if not DB_PATH.exists():
        print(f"❌ Banco de dados não encontrado: {DB_PATH}")
        return
    
    print("=" * 80)
    print("🔄 SCRIPT DE MESCLAGEM: JSONs ↔ Banco de Dados")
    print("=" * 80)
    print(f"Modo: {'SIMULAÇÃO (dry-run)' if dry_run else 'EXECUÇÃO REAL'}\n")
    
    # Buscar pedidos dos JSONs
    pedidos_json = get_all_json_pedidos()
    
    if not pedidos_json:
        print("❌ Nenhum pedido encontrado nos arquivos JSON!")
        return
    
    # Conectar ao banco
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # Buscar pedidos do banco
        print("📊 Verificando pedidos no banco de dados...")
        pedidos_db = get_database_pedidos(conn)
        print(f"✅ Encontrados {len(pedidos_db)} pedidos no banco de dados\n")
        
        # Identificar pedidos faltantes e com datas diferentes
        ids_json = set(pedidos_json.keys())
        ids_db = set(pedidos_db.keys())
        
        apenas_json = ids_json - ids_db
        em_ambos = ids_json & ids_db
        
        print("=" * 80)
        print("📋 ANÁLISE DE DIFERENÇAS")
        print("=" * 80)
        print(f"✅ Pedidos em ambos (JSON + BD): {len(em_ambos)}")
        print(f"⚠️ Pedidos apenas nos JSONs (faltando no BD): {len(apenas_json)}")
        print(f"⚠️ Pedidos apenas no BD (sem JSON): {len(ids_db - ids_json)}\n")
        
        # 1. Importar pedidos faltantes
        if apenas_json:
            print("=" * 80)
            print(f"📥 IMPORTAÇÃO DE PEDIDOS FALTANTES ({len(apenas_json)} pedidos)")
            print("=" * 80)
            
            importados = 0
            for pedido_id in sorted(apenas_json):
                pedido_data = pedidos_json[pedido_id]
                
                print(f"\n📦 Pedido ID {pedido_id}: {pedido_data.get('numero')} - {pedido_data.get('cliente')}")
                print(f"   Data entrada: {pedido_data.get('data_entrada')}")
                print(f"   Data entrega: {pedido_data.get('data_entrega')}")
                print(f"   Status: {pedido_data.get('status')}")
                
                if not dry_run:
                    if insert_pedido(conn, pedido_data, dry_run=False):
                        print(f"   ✅ Importado com sucesso!")
                        importados += 1
                    else:
                        print(f"   ⚠️ Não foi possível importar (já existe ou erro)")
                else:
                    print(f"   ⏸️  (simulação - seria importado)")
                    importados += 1
            
            if not dry_run:
                print(f"\n✅ {importados} pedidos importados com sucesso!")
            else:
                print(f"\n⏸️  Modo simulação - {importados} pedidos seriam importados")
        
        # 2. Corrigir datas de entrega incorretas
        print("\n" + "=" * 80)
        print("📅 CORREÇÃO DE DATAS DE ENTREGA")
        print("=" * 80)
        
        diferencas_data = []
        for pedido_id in em_ambos:
            pedido_json = pedidos_json[pedido_id]
            pedido_db = pedidos_db[pedido_id]
            
            json_data = normalize_date(pedido_json.get('data_entrega'))
            db_data = normalize_date(pedido_db.get('data_entrega'))
            
            if json_data and json_data != db_data:
                diferencas_data.append({
                    'id': pedido_id,
                    'numero': pedido_json.get('numero'),
                    'cliente': pedido_json.get('cliente'),
                    'json': json_data,
                    'db': db_data
                })
        
        if diferencas_data:
            print(f"\n⚠️ Encontradas {len(diferencas_data)} datas de entrega que precisam ser corrigidas:\n")
            print("-" * 80)
            
            corrigidas = 0
            for diff in diferencas_data:
                print(f"ID {diff['id']} ({diff['numero']}) - {diff['cliente']}")
                print(f"  BD atual: {diff['db']}")
                print(f"  JSON correto: {diff['json']}")
                
                if not dry_run:
                    if update_pedido_data_entrega(conn, diff['id'], diff['json'], dry_run=False):
                        print(f"  ✅ Corrigido!")
                        corrigidas += 1
                    else:
                        print(f"  ❌ Erro ao corrigir")
                else:
                    print(f"  ⏸️  (simulação - seria corrigido)")
                    corrigidas += 1
                print()
            
            if not dry_run:
                print(f"✅ {corrigidas} datas corrigidas com sucesso!")
            else:
                print(f"⏸️  Modo simulação - {corrigidas} datas seriam corrigidas")
        else:
            print("\n✅ Todas as datas de entrega estão corretas!")
        
        # Resumo final
        print("\n" + "=" * 80)
        print("✅ MESCLAGEM CONCLUÍDA")
        print("=" * 80)
        
        if dry_run:
            print("\n⚠️  Modo simulação - nenhuma alteração foi feita")
            print("   Execute com --execute para aplicar as mudanças")
        else:
            print("\n✅ Todas as operações foram executadas com sucesso!")
        
    except Exception as e:
        print(f"\n❌ Erro durante a mesclagem: {e}")
        import traceback
        traceback.print_exc()
        if not dry_run:
            conn.rollback()
    finally:
        conn.close()

def main():
    dry_run = '--execute' not in sys.argv
    merge_json_with_database(dry_run=dry_run)

if __name__ == "__main__":
    main()

