# API Sistema de Gestão de Produção (SGP)

API para gerenciamento de pedidos de produção gráfica, desenvolvida com FastAPI e SQLModel.

## 🚀 Características

- **FastAPI**: Framework moderno e rápido para APIs
- **SQLModel**: ORM moderno baseado em Pydantic e SQLAlchemy
- **SQLite**: Banco de dados simples e eficiente
- **Validação automática**: Schemas Pydantic para validação de dados
- **Documentação automática**: Swagger UI em `/docs`

## 📋 Estrutura do Projeto

```
api-sgp/
├── pedidos/           # Módulo de pedidos
│   ├── schema.py      # Schemas SQLModel
│   └── router.py      # Rotas da API
├── database/          # Configuração do banco
│   └── database.py    # Engine e sessões SQLModel
├── main.py            # Aplicação principal
├── base.py            # Configurações base
└── config.py          # Configurações da aplicação
```

## 🛠️ Instalação

1. **Clone o repositório**
```bash
git clone <url-do-repositorio>
cd api-sgp
```

2. **Instale as dependências**
```bash
pip install -r requirements.txt
```

3. **Execute a aplicação**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 Endpoints da API

### Pedidos

#### POST `/api/v1/pedidos/`
Cria um novo pedido.

**Exemplo de JSON:**
```json
{
  "numero": "1",
  "data_entrada": "2024-01-15",
  "data_entrega": "2024-01-20",
  "observacao": "Pedido urgente para evento",
  "prioridade": "ALTA",
  "status": "pendente",
  
  "cliente": "João Silva",
  "telefone_cliente": "(11) 99999-9999",
  "cidade_cliente": "São Paulo",
  
  "valor_total": "450.00",
  "valor_frete": "25.00",
  "valor_itens": "425.00",
  "tipo_pagamento": "1",
  "obs_pagamento": "2x sem juros",
  
  "forma_envio": "Sedex",
  "forma_envio_id": 1,
  
  "items": [
    {
      "id": 1,
      "tipo_producao": "painel",
      "descricao": "Painel de Fundo para Evento",
      "largura": "3.00",
      "altura": "2.50",
      "metro_quadrado": "7.50",
      "vendedor": "Maria Santos",
      "designer": "Carlos Lima",
      "tecido": "Banner",
      "acabamento": {
        "overloque": true,
        "elastico": false,
        "ilhos": true
      },
      "emenda": "sem-emenda",
      "observacao": "Impressão em alta resolução",
      "valor_unitario": "250.00",
      "imagem": "data:image/jpeg;base64,..."
    }
  ],
  
  "financeiro": false,
  "sublimacao": false,
  "costura": false,
  "expedicao": false
}
```

#### GET `/api/v1/pedidos/`
Lista todos os pedidos.

#### GET `/api/v1/pedidos/{pedido_id}`
Obtém um pedido específico por ID.

#### PATCH `/api/v1/pedidos/{pedido_id}`
Atualiza um pedido existente (aceita atualizações parciais).

#### DELETE `/api/v1/pedidos/{pedido_id}`
Deleta um pedido.

#### GET `/api/v1/pedidos/status/{status}`
Lista pedidos por status específico.

#### GET `/api/v1/pedidos/imagens/{imagem_id}`
Retorna o arquivo físico associado a um item de pedido.  
Envie o campo `imagem` dos itens como `data:image/<tipo>;base64,...` (mesmo formato já aceito) e a API armazenará o arquivo dentro de `MEDIA_ROOT`, retornando apenas uma URL para download quando o pedido for listado.

## 🗄️ Estrutura do Banco

### Tabela `pedidos`
- **id**: Chave primária
- **numero**: Número do pedido
- **data_entrada**: Data de entrada
- **data_entrega**: Data de entrega
- **observacao**: Observações do pedido
- **prioridade**: NORMAL ou ALTA
- **status**: pendente, em_producao, pronto, entregue, cancelado
- **cliente**: Nome do cliente
- **telefone_cliente**: Telefone do cliente
- **cidade_cliente**: Cidade do cliente
- **valor_total**: Valor total do pedido
- **valor_frete**: Valor do frete
- **valor_itens**: Valor dos itens
- **tipo_pagamento**: Tipo de pagamento
- **obs_pagamento**: Observações do pagamento
- **forma_envio**: Forma de envio
- **forma_envio_id**: ID da forma de envio
- **financeiro**: Status financeiro
- **sublimacao**: Status de sublimação
- **costura**: Status de costura
- **expedicao**: Status de expedição
- **items**: JSON com os itens do pedido
- **data_criacao**: Data de criação
- **ultima_atualizacao**: Data da última atualização

### Tabela `pedido_imagens`
- **id**: Chave primária
- **pedido_id**: Referência ao pedido
- **item_index/item_identificador**: Relação com o item correspondente
- **filename / mime_type**: Metadados do arquivo original
- **path**: Caminho relativo dentro de `MEDIA_ROOT`
- **tamanho / criado_em**: Informações de auditoria

## 🧪 Testes

Execute o script de teste para verificar se a API está funcionando:

```bash
python test_pedido.py
```

## 🧪 Dados de Exemplo

Para popular o banco com pedidos de diferentes status e validar o comportamento do frontend/API, execute:

```bash
python scripts/seed_pedidos.py --amount 10
```

Use `--amount` (`-n`) para informar quantos pedidos deseja inserir. O script gera registros distribuídos entre os status (pendente, em produção, pronto, entregue e cancelado) e é idempotente, ou seja, não duplica números já existentes.

## 📖 Documentação da API

Acesse a documentação interativa da API em:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🔧 Configuração

As configurações podem ser alteradas no arquivo `config.py` ou através de variáveis de ambiente:

- `DATABASE_URL`: URL do banco de dados
- `MEDIA_ROOT`: Diretório onde as imagens dos pedidos serão persistidas
- `MAX_IMAGE_SIZE_MB`: Tamanho máximo aceito para upload via base64
- `API_V1_STR`: Prefixo da API
- `PROJECT_NAME`: Nome do projeto
- `VERSION`: Versão da API
- `BACKEND_CORS_ORIGINS`: Origens permitidas para CORS

## 🚀 Melhorias Implementadas

- ✅ **SQLModel apenas**: Removida dependência do SQLAlchemy
- ✅ **Schemas modernos**: Estrutura Pydantic atualizada
- ✅ **Validação robusta**: Enums para status e prioridade
- ✅ **JSON nativo**: Items armazenados como JSON no banco
- ✅ **Tratamento de erros**: Try/catch com rollback
- ✅ **Documentação**: Docstrings em todas as funções
- ✅ **Testes**: Script de teste completo

## 📝 Notas

- A API agora usa apenas SQLModel para ORM
- Os items são armazenados como JSON no banco de dados
- Validação automática de todos os campos
- Suporte a diferentes tipos de produção (painel, totem, lona)
- Timestamps automáticos de criação e atualização
