# Especificação da API de Relatórios de Fechamentos

## Visão Geral

Esta especificação define a rota da API que processa relatórios de fechamentos de pedidos. O backend deve processar todos os dados e retornar o relatório completo já formatado, sem necessidade de processamento no frontend.

## Rota Principal

GET /relatorios-fechamentos/pedidos/relatorio

## Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `report_type` | string | Sim | Tipo de relatório (ver tipos abaixo) |
| `start_date` | string | Não | Data inicial no formato `YYYY-MM-DD` |
| `end_date` | string | Não | Data final no formato `YYYY-MM-DD` |
| `status` | string | Não | Status do pedido: `"Pendente"`, `"Em Processamento"`, `"Concluido"`, `"Cancelado"` ou `"Todos"` |
| `date_mode` | string | Não | Modo de referência de data: `"entrada"`, `"entrega"` ou `"qualquer"` |
| `vendedor` | string | Não | Filtro parcial (case-insensitive) por nome do vendedor |
| `designer` | string | Não | Filtro parcial (case-insensitive) por nome do designer |
| `cliente` | string | Não | Filtro parcial (case-insensitive) por nome do cliente |
| `frete_distribution` | string | Não | `"por_pedido"` (padrão) ou `"proporcional"` |

## Tipos de Relatórios

### Relatórios Analíticos (2 níveis de agrupamento)

1. **`analitico_designer_cliente`**
   - Agrupa por: Designer → Cliente
   - Estrutura: `groups[].subgroups[].rows[]`
   - Cada linha = 1 item de pedido

2. **`analitico_cliente_designer`**
   - Agrupa por: Cliente → Designer
   - Estrutura: `groups[].subgroups[].rows[]`
   - Cada linha = 1 item de pedido

3. **`analitico_cliente_painel`**
   - Agrupa por: Cliente → Tipo de Produção
   - Estrutura: `groups[].subgroups[].rows[]`
   - Cada linha = 1 item de pedido

4. **`analitico_designer_painel`**
   - Agrupa por: Designer → Tipo de Produção
   - Estrutura: `groups[].subgroups[].rows[]`
   - Cada linha = 1 item de pedido

5. **`analitico_entrega_painel`**
   - Agrupa por: Forma de Entrega → Tipo de Produção
   - Estrutura: `groups[].subgroups[].rows[]`
   - Cada linha = 1 item de pedido

6. **`analitico_vendedor_designer`**
   - Agrupa por: Vendedor → Designer
   - Estrutura: `groups[].subgroups[].rows[]`
   - Cada linha = 1 item de pedido

7. **`analitico_designer_vendedor`**
   - Agrupa por: Designer → Vendedor
   - Estrutura: `groups[].subgroups[].rows[]`
   - Cada linha = 1 item de pedido

### Relatórios Sintéticos (1 nível de agrupamento)

8. **`sintetico_data`**
   - Agrupa por: Data (referência automática: entrega → entrada)
   - Estrutura: `groups[].rows[]` (sem subgroups)
   - Cada grupo tem apenas 1 linha com descrição agregada

9. **`sintetico_data_entrada`**
   - Agrupa por: Data de Entrada
   - Estrutura: `groups[].rows[]` (sem subgroups)
   - Cada grupo tem apenas 1 linha com descrição agregada

10. **`sintetico_data_entrega`**
   - Agrupa por: Data de Entrega
   - Estrutura: `groups[].rows[]` (sem subgroups)
   - Cada grupo tem apenas 1 linha com descrição agregada

11. **`sintetico_designer`**
   - Agrupa por: Designer
   - Estrutura: `groups[].rows[]` (sem subgroups)
   - Cada grupo tem apenas 1 linha com descrição agregada

12. **`sintetico_vendedor`**
    - Agrupa por: Vendedor
    - Estrutura: `groups[].rows[]` (sem subgroups)
    - Cada grupo tem apenas 1 linha com descrição agregada

13. **`sintetico_vendedor_designer`**
    - Agrupa por: Vendedor/Designer (combinado)
    - Estrutura: `groups[].rows[]` (sem subgroups)
    - Cada grupo tem apenas 1 linha com descrição agregada
    - **IMPORTANTE**: Usar `frete_distribution: "proporcional"` para evitar duplicação de frete

14. **`sintetico_cliente`**
    - Agrupa por: Cliente
    - Estrutura: `groups[].rows[]` (sem subgroups)
    - Cada grupo tem apenas 1 linha com descrição agregada

15. **`sintetico_entrega`**
    - Agrupa por: Forma de Entrega
    - Estrutura: `groups[].rows[]` (sem subgroups)
    - Cada grupo tem apenas 1 linha com descrição agregada

## Estrutura de Resposta

### Schema JSON

```
{
  "title": "string",
  "period_label": "string",
  "status_label": "string",
  "page": 1,
  "generated_at": "string",
  "report_type": "string",
  "groups": [
    {
      "key": "string",
      "label": "string",
      "rows": [
        {
          "ficha": "string",
          "descricao": "string",
          "valor_frete": 0.00,
          "valor_servico": 0.00
        }
      ],
      "subgroups": [
        {
          "key": "string",
          "label": "string",
          "rows": [
            {
              "ficha": "string",
              "descricao": "string",
              "valor_frete": 0.00,
              "valor_servico": 0.00
            }
          ],
          "subtotal": {
            "valor_frete": 0.00,
            "valor_servico": 0.00,
            "desconto": 0.00,
            "valor_liquido": 0.00
          }
        }
      ],
      "subtotal": {
        "valor_frete": 0.00,
        "valor_servico": 0.00,
        "desconto": 0.00,
        "valor_liquido": 0.00
      }
    }
  ],
  "total": {
    "valor_frete": 0.00,
    "valor_servico": 0.00,
    "desconto": 0.00,
    "valor_liquido": 0.00
  }
}
```

## Campos da Resposta

### title (string)

Título do relatório baseado no tipo:

- analitico_designer_cliente → "Relatório Analítico — Designer × Cliente"
- analitico_cliente_designer → "Relatório Analítico — Cliente × Designer"
- analitico_cliente_painel → "Relatório Analítico — Cliente × Tipo de Produção"
- analitico_designer_painel → "Relatório Analítico — Designer × Tipo de Produção"
- analitico_entrega_painel → "Relatório Analítico — Forma de Entrega × Tipo de Produção"
- analitico_vendedor_designer → "Relatório Analítico — Vendedor × Designer"
- analitico_designer_vendedor → "Relatório Analítico — Designer × Vendedor"
- sintetico_data → "Relatório Sintético — Totais por Data (referência automática)"
- sintetico_data_entrada → "Relatório Sintético — Totais por Data de Entrada"
- sintetico_data_entrega → "Relatório Sintético — Totais por Data de Entrega"
- sintetico_designer → "Relatório Sintético — Totais por Designer"
- sintetico_vendedor → "Relatório Sintético — Totais por Vendedor"
- sintetico_vendedor_designer → "Relatório Sintético — Totais por Vendedor/Designer"
- sintetico_cliente → "Relatório Sintético — Totais por Cliente"
- sintetico_entrega → "Relatório Sintético — Totais por Forma de Entrega"

### period_label (string)

Formato: "Período: DD/MM/YYYY - DD/MM/YYYY" ou "Período: DD/MM/YYYY" ou "Período não especificado"

### status_label (string)

Formato: "Status: {status}" onde status pode ser: "Todos", "Pendente", "Em Processamento", "Concluído", "Cancelado"

### page (integer)

Sempre retornar 1 (paginação não implementada)

### generated_at (string)

Data/hora de geração no formato brasileiro: "DD/MM/YYYY, HH:MM:SS"

### report_type (string)

O mesmo valor do parâmetro report_type recebido

### groups (array)

Array de grupos do relatório. Cada grupo pode ter:

- key: Identificador único (slug) do grupo
- label: Nome do grupo para exibição
- rows: Array de linhas (apenas para sintéticos ou itens de subgrupos)
- subgroups: Array de subgrupos (apenas para analíticos)
- subtotal: Totais do grupo

### rows (array)

Array de linhas do relatório. Cada linha contém:

- ficha: Número da ficha/pedido (ou descrição agregada para sintéticos)
- descricao: Descrição do item (ou "Subtotal" para sintéticos)
- valor_frete: Valor do frete (número com 2 casas decimais)
- valor_servico: Valor do serviço/item (número com 2 casas decimais)

Para relatórios sintéticos: Cada grupo tem apenas 1 linha onde:

- ficha: Descrição agregada no formato "Pedidos: {quantidade} · Itens: {quantidade}"
- descricao: Sempre "Subtotal"

### subtotal (object)

Totais do grupo/subgrupo:

- valor_frete: Soma dos valores de frete (número com 2 casas decimais)
- valor_servico: Soma dos valores de serviço (número com 2 casas decimais)
- desconto: Desconto aplicado (opcional, número com 2 casas decimais)
- valor_liquido: Valor líquido = frete + serviço - desconto (opcional, número com 2 casas decimais)

### total (object)

Totais gerais do relatório (mesma estrutura de subtotal)

## Regras de Negócio

### 1. Filtragem de Pedidos

#### Por Status

- Se status = "Todos" ou não informado: incluir todos os status
- Caso contrário: filtrar apenas pedidos com o status especificado

Mapeamento de status:

- "Pendente" → status pendente
- "Em Processamento" → status em_producao
- "Concluido" → status pronto ou entregue
- "Cancelado" → status cancelado

#### Por Data

- Se date_mode = "entrada": usar data_entrada do pedido
- Se date_mode = "entrega": usar data_entrega do pedido
- Se date_mode = "qualquer": incluir pedido se data_entrada OU data_entrega estiver no período
- Se date_mode não informado: usar fallback data_entrega → data_entrada

#### Por Pessoas (Vendedor/Designer/Cliente)

- Busca parcial (case-insensitive)
- Aplicar nos itens dos pedidos (não no pedido em si)
- Se vendedor informado: filtrar itens onde vendedor contém o valor (parcial)
- Se designer informado: filtrar itens onde designer contém o valor (parcial)
- Se cliente informado: filtrar pedidos onde cliente contém o valor (parcial)

### 2. Cálculo de Valores

#### Valor do Serviço (por item)

- Calcular: quantity * unit_price ou usar subtotal do item
- Arredondar para 2 casas decimais

#### Valor do Frete

Modo por_pedido (padrão):

- Cada item de um pedido mostra o frete total do pedido
- No total geral: contar o frete apenas uma vez por pedido (não somar múltiplas vezes)

Exemplo: Pedido com 3 itens e frete de R$ 50,00

- Item 1: frete = R$ 50,00
- Item 2: frete = R$ 50,00
- Item 3: frete = R$ 50,00
- Total geral: frete = R$ 50,00 (não R$ 150,00)

Modo proporcional:

- Distribuir o frete proporcionalmente entre os itens do pedido
- Fórmula: frete_item = (valor_item / total_itens) * frete_total

Exemplo: Pedido com frete R$ 50,00 e 2 itens (R$ 100,00 e R$ 200,00)

- Item 1: frete = R$ 16,67 (50 * 100/300)
- Item 2: frete = R$ 33,33 (50 * 200/300)
- Total geral: frete = R$ 50,00

IMPORTANTE: Para sintetico_vendedor_designer, sempre usar modo proporcional para evitar duplicação de frete quando um pedido aparece em múltiplos grupos.

#### Desconto

- Calcular: (soma_itens + frete) - valor_total (se positivo)
- Aplicar apenas uma vez por pedido no total geral
- Incluir no subtotal e total apenas se houver desconto > 0

#### Valor Líquido

- Calcular: valor_frete + valor_servico - desconto
- Incluir apenas se houver desconto

### 3. Agrupamento

#### Relatórios Analíticos

- Criar grupos de primeiro nível conforme o primeiro critério
- Dentro de cada grupo, criar subgrupos conforme o segundo critério
- Cada subgrupo contém as linhas (itens) que pertencem a ambos os critérios
- Ordenar grupos e subgrupos alfabeticamente (case-insensitive, considerando acentos)

#### Relatórios Sintéticos

- Criar grupos conforme o critério de agrupamento
- Cada grupo contém apenas 1 linha com descrição agregada
- A linha deve ter:
  - ficha: "Pedidos: {quantidade_pedidos_unicos} · Itens: {quantidade_itens}"
  - descricao: "Subtotal"
- Ordenar grupos alfabeticamente (case-insensitive, considerando acentos)

### 4. Normalização de Dados

#### Campos que podem estar vazios

- vendedor: usar "Sem vendedor" se vazio
- designer: usar "Sem designer" se vazio
- tipo_producao: usar "Sem tipo" se vazio
- cliente: usar "Cliente não informado" se vazio
- forma_envio: usar "Sem forma de envio" se vazio
- numero (ficha): usar id do pedido se vazio

#### Formatação de Datas

- Para period_label: formatar como DD/MM/YYYY
- Para agrupamento por data: usar DD/MM/YYYY como chave e label

#### Geração de Keys (slugs)

- Converter labels para slugs (lowercase, sem acentos, espaços viram hífens)

Exemplo: "Designer: João Silva" → "designer-joao-silva"

## Exemplo de Requisição

GET /relatorios-fechamentos/pedidos/relatorio?report_type=analitico_designer_cliente&start_date=2024-01-01&end_date=2024-01-31&status=Todos&date_mode=entrega

## Exemplo de Resposta

```
{
  "title": "Relatório Analítico — Designer × Cliente",
  "period_label": "Período: 01/01/2024 - 31/01/2024",
  "status_label": "Status: Todos",
  "page": 1,
  "generated_at": "01/02/2024, 14:30:00",
  "report_type": "analitico_designer_cliente",
  "groups": [
    {
      "key": "designer-joao-silva",
      "label": "Designer: João Silva",
      "subgroups": [
        {
          "key": "cliente-empresa-abc",
          "label": "Cliente: Empresa ABC",
          "rows": [
            {
              "ficha": "123",
              "descricao": "Banner 2x1m",
              "valor_frete": 50.00,
              "valor_servico": 200.00
            },
            {
              "ficha": "123",
              "descricao": "Banner 3x2m",
              "valor_frete": 50.00,
              "valor_servico": 300.00
            }
          ],
          "subtotal": {
            "valor_frete": 50.00,
            "valor_servico": 500.00
          }
        }
      ],
      "subtotal": {
        "valor_frete": 50.00,
        "valor_servico": 500.00
      }
    }
  ],
  "total": {
    "valor_frete": 50.00,
    "valor_servico": 500.00
  }
}
```

## Exemplo de Resposta Sintética

```
{
  "title": "Relatório Sintético — Totais por Vendedor",
  "period_label": "Período: 01/01/2024 - 31/01/2024",
  "status_label": "Status: Todos",
  "page": 1,
  "generated_at": "01/02/2024, 14:30:00",
  "report_type": "sintetico_vendedor",
  "groups": [
    {
      "key": "vendedor-maria-santos",
      "label": "Vendedor: Maria Santos",
      "rows": [
        {
          "ficha": "Pedidos: 12 · Itens: 27",
          "descricao": "Subtotal",
          "valor_frete": 600.00,
          "valor_servico": 5400.00
        }
      ],
      "subtotal": {
        "valor_frete": 600.00,
        "valor_servico": 5400.00
      }
    }
  ],
  "total": {
    "valor_frete": 600.00,
    "valor_servico": 5400.00
  }
}
```

## Tratamento de Erros

### Erro 400 - Bad Request

Retornar quando:

- report_type não for um dos 15 tipos válidos
- start_date > end_date
- formato de data inválido

### Erro 500 - Internal Server Error

Retornar quando:

- erro ao processar dados do banco
- erro ao calcular totais
