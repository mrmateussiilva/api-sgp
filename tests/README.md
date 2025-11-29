# Testes do Backend SGP

Esta pasta contém a suíte completa de testes automatizados para o backend da API SGP.

## Estrutura

- `conftest.py`: Configuração global de fixtures (banco em memória, cliente HTTP)
- `test_pedidos.py`: Testes de criação, listagem, atualização e filtros de pedidos
- `test_notificacoes.py`: Testes do endpoint de notificações (ultimo_id, timestamp)
- `test_validacoes.py`: Testes de validação de campos obrigatórios e regras de negócio

## Executando os Testes

### Instalar dependências

```bash
pip install -r requirements.txt
```

### Rodar todos os testes

```bash
pytest tests/
```

### Rodar testes específicos

```bash
# Apenas testes de pedidos
pytest tests/test_pedidos.py

# Apenas testes de notificações
pytest tests/test_notificacoes.py

# Com verbose
pytest tests/ -v
```

### Com coverage

```bash
pytest tests/ --cov=. --cov-report=html
```

## Características

- **Banco em memória**: Cada teste usa SQLite em memória, isolado dos outros
- **Fixtures**: Configuração automática de banco e cliente HTTP
- **Assíncrono**: Todos os testes são assíncronos usando pytest-asyncio
- **Isolamento**: Cada teste limpa o banco antes de executar

## Notas

- Os testes não dependem da intranet ou banco de dados real
- O contador global `ULTIMO_PEDIDO_ID` é resetado entre testes quando necessário
- Todos os endpoints são testados com dados mockados

