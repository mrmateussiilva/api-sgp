# 🗄️ SQLite Viewer

Aplicação web interativa em Python usando Streamlit para analisar e visualizar dados de bancos SQLite.

## 📋 Funcionalidades

### ✅ Upload e Conexão
- Upload de arquivos .db/.sqlite através da interface
- Conexão por caminho local do arquivo
- Validação automática de arquivos SQLite válidos

### ✅ Explorador de Tabelas
- Visualização de todas as tabelas do banco
- Informações detalhadas sobre colunas e tipos de dados
- Visualização de dados com paginação configurável
- Número total de registros e informações do banco

### ✅ Detector de Duplicatas
- **Duplicatas Completas**: Linhas 100% idênticas
  - Mostra quantidade de duplicatas
  - Exibe linhas duplicadas destacadas
  - Botão para exportar duplicatas
  
- **Duplicatas por Coluna**: 
  - Análise de valores únicos vs total de valores
  - Gráfico de barras dos valores mais repetidos
  - Top 10 valores duplicados com contagens
  
- **Duplicatas por Combinação de Colunas**:
  - Seleção de 2-3 colunas para análise
  - Identificação de registros com mesma combinação
  - Visualização de grupos de duplicatas

### ✅ Visualizações
- **Distribuição de Dados**:
  - Histogramas para colunas numéricas
  - Box plots para análise estatística
  
- **Dados Categóricos**:
  - Gráficos de pizza para distribuição
  - Gráficos de barras para top valores
  
- **Análise de Valores Nulos**:
  - Heatmap de valores nulos por coluna
  
- **Análise Temporal**:
  - Gráficos de linha do tempo (se houver colunas de data)

### ✅ Estatísticas
- Resumo estatístico completo (min, max, média, mediana)
- Contagem de valores nulos por coluna
- Distribuição de tipos de dados
- Tamanho do banco de dados e uso de memória

### ✅ Busca e Filtros
- Campo de busca geral para filtrar dados em todas as colunas
- Filtros por coluna com operadores (=, !=, >, <, >=, <=, LIKE, NOT LIKE)
- Execução de queries SQL customizadas
- Exportação de resultados filtrados

### ✅ Exportação
- Exportar dados para CSV
- Exportar dados para Excel (XLSX)
- Exportar duplicatas identificadas
- Exportar resultados de queries e filtros

## 🚀 Instalação

### Pré-requisitos

- Python 3.8 ou superior
- pip ou gerenciador de pacotes Python

### Passos

1. Navegue até o diretório do módulo:

```bash
cd sqlite_viewer
```

2. Crie um ambiente virtual (recomendado):

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

## 💻 Uso

Execute a aplicação com uma das opções abaixo:

### Opção 1: Usando Streamlit diretamente
```bash
streamlit run app.py
```

### Opção 2: Usando scripts de execução
**Linux/Mac:**
```bash
./run.sh
```

**Windows:**
```batch
run.bat
```

A aplicação será aberta automaticamente no seu navegador em `http://localhost:8501`.

### Como Usar

1. **Conectar ao Banco**:
   - Faça upload de um arquivo .db ou .sqlite usando a barra lateral
   - Ou digite o caminho completo do arquivo local

2. **Explorar Dados**:
   - Selecione uma tabela na barra lateral
   - Visualize os dados na aba "📊 Explorador"
   - Configure limites de linhas para melhor performance

3. **Analisar Duplicatas**:
   - Vá para a aba "🔍 Análise de Duplicatas"
   - Explore duplicatas completas, por coluna ou por combinação
   - Exporte resultados para análise posterior

4. **Visualizar Gráficos**:
   - Use a aba "📈 Visualizações" para criar gráficos interativos
   - Explore distribuições, valores categóricos e valores nulos

5. **Ver Estatísticas**:
   - A aba "📉 Estatísticas" mostra um resumo completo dos dados
   - Analise valores nulos e tipos de dados

6. **Buscar e Filtrar**:
   - Use a aba "🔎 Busca e Filtros" para encontrar dados específicos
   - Execute queries SQL customizadas para análises avançadas

7. **Exportar**:
   - Use os botões de download para exportar dados em CSV ou Excel
   - Exporte duplicatas, filtros e resultados de queries

## 📦 Estrutura do Projeto

```
sqlite_viewer/
├── __init__.py           # Inicialização do pacote
├── app.py                # Aplicação principal Streamlit
├── database.py           # Funções de conexão e operações com banco
├── analysis.py           # Funções de análise de duplicatas e estatísticas
├── visualizations.py     # Funções de criação de gráficos
├── exports.py            # Funções de exportação de dados
├── requirements.txt      # Dependências do projeto
├── run.sh                # Script de execução (Linux/Mac)
├── run.bat               # Script de execução (Windows)
└── README.md             # Este arquivo
```

## 🛠️ Tecnologias Utilizadas

- **Streamlit**: Framework web para aplicações Python
- **Pandas**: Manipulação e análise de dados
- **Plotly**: Gráficos interativos
- **Polars**: Processamento de dados de alta performance (opcional)
- **OpenPyXL**: Exportação para Excel
- **SQLite3**: Banco de dados SQLite (built-in Python)

## 📝 Notas Importantes

- A aplicação mantém o banco de dados aberto durante a sessão para melhor performance
- Para bancos muito grandes, considere usar filtros ou limites de linhas nas visualizações
- Queries SQL customizadas devem ser usadas com cuidado - validação limitada
- Arquivos temporários de upload são mantidos durante a sessão do Streamlit
- Use `st.cache_data` para otimizar carregamento de dados repetidos

## 🔧 Funcionalidades Técnicas

- **Cache de dados**: Uso extensivo de `st.cache_data` para otimizar performance
- **Modular**: Código organizado em módulos separados por funcionalidade
- **Tratamento de erros**: Validações e mensagens de erro claras
- **Interface responsiva**: Layout adaptável usando `st.columns()` e `st.tabs()`
- **Feedback visual**: Mensagens de sucesso, erro e aviso claras

## 📄 Licença

Este projeto é open source e está disponível para uso livre.

## 🤝 Contribuições

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

## 🐛 Reportar Problemas

Se encontrar algum problema ou tiver sugestões, por favor abra uma issue no repositório.

