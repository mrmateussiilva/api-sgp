"""
Aplicação Streamlit principal para visualização e análise de bancos SQLite.
"""

import streamlit as st
import sqlite3
import pandas as pd
import tempfile
from pathlib import Path
import os

# Importar módulos locais
try:
    from .database import (
        validate_sqlite_file,
        get_tables,
        get_table_info,
        get_table_data,
        get_row_count,
        execute_custom_query,
        get_database_size
    )
    from .analysis import (
        get_duplicate_rows,
        get_duplicate_values_by_column,
        get_duplicate_combinations,
        get_statistical_summary,
        get_null_statistics,
        get_data_types_distribution,
        filter_dataframe,
        search_in_dataframe,
        detect_date_columns
    )
    from .visualizations import (
        create_null_heatmap,
        create_histogram,
        create_box_plot,
        create_pie_chart,
        create_bar_chart,
        create_time_series,
        create_duplicates_bar_chart
    )
    from .exports import export_to_csv, export_to_excel
except ImportError:
    # Para execução direta do script
    from database import (
        validate_sqlite_file,
        get_tables,
        get_table_info,
        get_table_data,
        get_row_count,
        execute_custom_query,
        get_database_size
    )
    from analysis import (
        get_duplicate_rows,
        get_duplicate_values_by_column,
        get_duplicate_combinations,
        get_statistical_summary,
        get_null_statistics,
        get_data_types_distribution,
        filter_dataframe,
        search_in_dataframe,
        detect_date_columns
    )
    from visualizations import (
        create_null_heatmap,
        create_histogram,
        create_box_plot,
        create_pie_chart,
        create_bar_chart,
        create_time_series,
        create_duplicates_bar_chart
    )
    from exports import export_to_csv, export_to_excel


# Configuração da página
st.set_page_config(
    page_title="SQLite Viewer",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)


def initialize_session_state():
    """Inicializa variáveis de sessão."""
    if 'db_path' not in st.session_state:
        st.session_state.db_path = None
    if 'conn' not in st.session_state:
        st.session_state.conn = None


def render_connection_sidebar():
    """Renderiza barra lateral para conexão com banco."""
    with st.sidebar:
        st.header("📂 Conexão com Banco")
        
        # Opção 1: Upload de arquivo
        uploaded_file = st.file_uploader(
            "Enviar arquivo .db ou .sqlite",
            type=['db', 'sqlite', 'sqlite3'],
            help="Envie um arquivo de banco SQLite"
        )
        
        if uploaded_file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_path = tmp_file.name
            
            if validate_sqlite_file(tmp_path):
                st.session_state.db_path = tmp_path
                st.session_state.conn = sqlite3.connect(tmp_path)
                st.success("✅ Banco carregado com sucesso!")
            else:
                st.error("❌ Arquivo inválido. Por favor, envie um banco SQLite válido.")
        
        # Opção 2: Caminho local
        st.markdown("---")
        st.subheader("Ou")
        local_path = st.text_input(
            "Caminho do arquivo local",
            help="Digite o caminho completo do arquivo .db ou .sqlite"
        )
        
        if local_path and Path(local_path).exists():
            if validate_sqlite_file(local_path):
                st.session_state.db_path = local_path
                st.session_state.conn = sqlite3.connect(local_path)
                st.success("✅ Banco conectado com sucesso!")
            else:
                st.error("❌ Arquivo inválido.")
        elif local_path:
            st.warning("⚠️ Arquivo não encontrado.")


def render_explorer_tab(selected_table: str):
    """Renderiza aba de explorador de tabelas."""
    st.header(f"Tabela: {selected_table}")
    
    # Informações da tabela
    col1, col2, col3 = st.columns(3)
    
    with col1:
        row_count = get_row_count(st.session_state.conn, st.session_state.db_path, selected_table)
        st.metric("📊 Total de Registros", row_count)
    
    with col2:
        table_info = get_table_info(st.session_state.conn, st.session_state.db_path, selected_table)
        st.metric("📝 Número de Colunas", len(table_info))
    
    with col3:
        db_size = get_database_size(st.session_state.db_path)
        st.metric("💾 Tamanho do Banco", f"{db_size:.2f} MB")
    
    # Informações das colunas
    st.subheader("📋 Colunas")
    st.dataframe(
        table_info[['name', 'type', 'notnull', 'pk']].rename(columns={
            'name': 'Nome',
            'type': 'Tipo',
            'notnull': 'Não Nulo',
            'pk': 'Chave Primária'
        }),
        use_container_width=True,
        hide_index=True
    )
    
    # Dados da tabela
    st.subheader("📄 Dados")
    
    show_limit = st.checkbox("Limitar número de linhas", value=True)
    limit = None
    if show_limit:
        limit = st.slider("Linhas para exibir", 10, 10000, 100, 10)
    
    df_data = get_table_data(st.session_state.conn, st.session_state.db_path, selected_table, limit)
    
    if not df_data.empty:
        st.dataframe(df_data, use_container_width=True, height=400)
        
        # Exportar dados
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            csv_data = export_to_csv(df_data)
            st.download_button(
                label="📥 Exportar para CSV",
                data=csv_data,
                file_name=f"{selected_table}_dados.csv",
                mime="text/csv"
            )
        with col_exp2:
            excel_data = export_to_excel(df_data)
            st.download_button(
                label="📥 Exportar para Excel",
                data=excel_data,
                file_name=f"{selected_table}_dados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )


def render_duplicates_tab(selected_table: str):
    """Renderiza aba de análise de duplicatas."""
    st.header("🔍 Análise de Duplicatas")
    
    df_full = get_table_data(st.session_state.conn, st.session_state.db_path, selected_table)
    
    # Duplicatas completas
    st.subheader("1️⃣ Duplicatas Completas")
    st.markdown("Linhas 100% idênticas em todas as colunas")
    
    duplicate_rows, duplicate_count = get_duplicate_rows(df_full)
    
    col_dup1, col_dup2 = st.columns(2)
    with col_dup1:
        st.metric("Número de Duplicatas", duplicate_count)
    
    if duplicate_count > 0:
        with col_dup2:
            unique_duplicates = len(duplicate_rows.drop_duplicates())
            st.metric("Grupos Únicos", unique_duplicates)
        
        st.dataframe(duplicate_rows, use_container_width=True, height=300)
        
        # Exportar duplicatas
        dup_csv = export_to_csv(duplicate_rows)
        dup_excel = export_to_excel(duplicate_rows)
        
        col_exp_dup1, col_exp_dup2 = st.columns(2)
        with col_exp_dup1:
            st.download_button(
                "📥 Exportar Duplicatas (CSV)",
                dup_csv,
                f"{selected_table}_duplicatas.csv",
                mime="text/csv"
            )
        with col_exp_dup2:
            st.download_button(
                "📥 Exportar Duplicatas (Excel)",
                dup_excel,
                f"{selected_table}_duplicatas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.success("✅ Nenhuma duplicata completa encontrada!")
    
    st.markdown("---")
    
    # Duplicatas por coluna
    st.subheader("2️⃣ Duplicatas por Coluna")
    
    selected_column = st.selectbox(
        "Selecione uma coluna para análise",
        df_full.columns,
        key="dup_column_select"
    )
    
    if selected_column:
        dup_by_col = get_duplicate_values_by_column(df_full, selected_column)
        
        if not dup_by_col.empty:
            col_stat1, col_stat2 = st.columns(2)
            
            with col_stat1:
                unique_values = df_full[selected_column].nunique()
                st.metric("Valores Únicos", unique_values)
            
            with col_stat2:
                duplicate_unique = len(dup_by_col)
                st.metric("Valores Duplicados", duplicate_unique)
            
            # Top 10 valores duplicados
            st.subheader(f"Top 10 Valores Mais Duplicados em '{selected_column}'")
            top_10 = dup_by_col.head(10)
            
            # Gráfico de barras
            fig_bar = create_duplicates_bar_chart(dup_by_col, selected_column)
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # Tabela
            st.dataframe(top_10, use_container_width=True, hide_index=True)
        else:
            st.success(f"✅ Nenhum valor duplicado encontrado na coluna '{selected_column}'!")
    
    st.markdown("---")
    
    # Duplicatas por combinação de colunas
    st.subheader("3️⃣ Duplicatas por Combinação de Colunas")
    
    numeric_cols = df_full.select_dtypes(include=['object', 'string']).columns.tolist()
    if len(numeric_cols) < 2:
        numeric_cols = df_full.columns.tolist()[:3]
    
    selected_cols = st.multiselect(
        "Selecione 2-3 colunas para combinação",
        df_full.columns.tolist(),
        default=numeric_cols[:2] if len(numeric_cols) >= 2 else [],
        max_selections=3
    )
    
    if len(selected_cols) >= 2:
        dup_combinations = get_duplicate_combinations(df_full, selected_cols)
        
        if not dup_combinations.empty:
            st.metric("Combinações Duplicadas", len(dup_combinations))
            st.dataframe(dup_combinations, use_container_width=True, height=300)
            
            # Exportar
            comb_csv = export_to_csv(dup_combinations)
            st.download_button(
                "📥 Exportar Combinações Duplicadas (CSV)",
                comb_csv,
                f"{selected_table}_combinacoes_duplicadas.csv",
                mime="text/csv"
            )
        else:
            st.success("✅ Nenhuma combinação duplicada encontrada!")


def render_visualizations_tab(selected_table: str):
    """Renderiza aba de visualizações."""
    st.header("📊 Visualizações")
    
    df_viz = get_table_data(st.session_state.conn, st.session_state.db_path, selected_table, limit=5000)
    
    if df_viz.empty:
        st.warning("⚠️ Nenhum dado para visualizar.")
        return
    
    # Distribuição de dados
    st.subheader("Distribuição de Dados")
    
    # Colunas numéricas
    numeric_cols = df_viz.select_dtypes(include=['number']).columns.tolist()
    if numeric_cols:
        selected_num_col = st.selectbox("Selecione coluna numérica", numeric_cols, key="num_col_viz")
        
        if selected_num_col:
            col_hist1, col_hist2 = st.columns(2)
            
            with col_hist1:
                fig_hist = create_histogram(df_viz, selected_num_col)
                st.plotly_chart(fig_hist, use_container_width=True)
            
            with col_hist2:
                fig_box = create_box_plot(df_viz, selected_num_col)
                st.plotly_chart(fig_box, use_container_width=True)
    
    # Colunas categóricas
    st.markdown("---")
    st.subheader("Análise de Colunas Categóricas")
    
    categorical_cols = df_viz.select_dtypes(include=['object', 'string']).columns.tolist()
    if categorical_cols:
        selected_cat_col = st.selectbox("Selecione coluna categórica", categorical_cols, key="cat_col_viz")
        
        if selected_cat_col:
            value_counts = df_viz[selected_cat_col].value_counts().head(15)
            
            col_pie1, col_pie2 = st.columns(2)
            
            with col_pie1:
                fig_pie = create_pie_chart(value_counts, f"Distribuição - {selected_cat_col}")
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_pie2:
                fig_bar_cat = create_bar_chart(
                    value_counts.index.tolist(),
                    value_counts.values.tolist(),
                    selected_cat_col,
                    'Contagem',
                    f"Top 15 Valores - {selected_cat_col}"
                )
                st.plotly_chart(fig_bar_cat, use_container_width=True)
    
    # Heatmap de valores nulos
    st.markdown("---")
    st.subheader("Mapa de Calor - Valores Nulos")
    null_fig = create_null_heatmap(df_viz)
    st.plotly_chart(null_fig, use_container_width=True)
    
    # Gráfico de linha do tempo
    st.markdown("---")
    st.subheader("Análise Temporal (se aplicável)")
    
    date_cols = detect_date_columns(df_viz)
    
    if date_cols:
        selected_date_col = st.selectbox("Selecione coluna de data", date_cols, key="date_col_viz")
        
        if selected_date_col:
            fig_line = create_time_series(df_viz, selected_date_col)
            st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("ℹ️ Nenhuma coluna de data detectada para análise temporal.")


def render_statistics_tab(selected_table: str):
    """Renderiza aba de estatísticas."""
    st.header("📈 Estatísticas Descritivas")
    
    df_stats = get_table_data(st.session_state.conn, st.session_state.db_path, selected_table)
    
    # Resumo estatístico
    st.subheader("Resumo Estatístico")
    summary_df = get_statistical_summary(df_stats)
    
    if not summary_df.empty:
        st.dataframe(summary_df, use_container_width=True)
    else:
        st.info("ℹ️ Nenhuma coluna numérica encontrada.")
    
    # Valores nulos
    st.markdown("---")
    st.subheader("Valores Nulos por Coluna")
    null_df = get_null_statistics(df_stats)
    st.dataframe(null_df, use_container_width=True, hide_index=True)
    
    # Tipos de dados
    st.markdown("---")
    st.subheader("Distribuição de Tipos de Dados")
    type_df = get_data_types_distribution(df_stats)
    st.dataframe(type_df, use_container_width=True, hide_index=True)
    
    # Informações do banco
    st.markdown("---")
    st.subheader("Informações do Banco")
    info_col1, info_col2 = st.columns(2)
    
    with info_col1:
        st.metric("Total de Registros", len(df_stats))
        st.metric("Total de Colunas", len(df_stats.columns))
    
    with info_col2:
        db_size = get_database_size(st.session_state.db_path)
        st.metric("Tamanho do Banco (MB)", f"{db_size:.2f}")
        st.metric("Memória Usada (MB)", f"{df_stats.memory_usage(deep=True).sum() / (1024 * 1024):.2f}")


def render_search_tab(selected_table: str):
    """Renderiza aba de busca e filtros."""
    st.header("🔎 Busca e Filtros")
    
    df_filter = get_table_data(st.session_state.conn, st.session_state.db_path, selected_table)
    
    # Busca geral
    st.subheader("Busca Geral")
    search_term = st.text_input("Digite o termo de busca", help="Busca em todas as colunas")
    
    if search_term:
        df_filtered = search_in_dataframe(df_filter, search_term)
        st.success(f"✅ {len(df_filtered)} registros encontrados")
        st.dataframe(df_filtered, use_container_width=True, height=400)
    else:
        st.dataframe(df_filter, use_container_width=True, height=400)
    
    st.markdown("---")
    
    # Filtros por coluna
    st.subheader("Filtros por Coluna")
    
    filter_col = st.selectbox("Selecione coluna para filtrar", df_filter.columns, key="filter_col")
    filter_operator = st.selectbox(
        "Operador",
        ["=", "!=", ">", "<", ">=", "<=", "LIKE", "NOT LIKE"],
        key="filter_op"
    )
    filter_value = st.text_input("Valor", key="filter_val")
    
    if filter_value:
        try:
            df_filtered = filter_dataframe(df_filter, filter_col, filter_operator, filter_value)
            st.success(f"✅ {len(df_filtered)} registros após filtro")
            st.dataframe(df_filtered, use_container_width=True, height=400)
            
            # Exportar filtrado
            if not df_filtered.empty:
                filtered_csv = export_to_csv(df_filtered)
                st.download_button(
                    "📥 Exportar Resultado do Filtro (CSV)",
                    filtered_csv,
                    f"{selected_table}_filtrado.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"❌ Erro ao aplicar filtro: {str(e)}")
    
    st.markdown("---")
    
    # Query SQL customizada
    st.subheader("Query SQL Customizada")
    st.warning("⚠️ Use com cuidado! Queries mal formatadas podem causar erros.")
    
    custom_query = st.text_area(
        "Digite sua query SQL",
        height=150,
        help="Exemplo: SELECT * FROM tabela WHERE coluna = 'valor'"
    )
    
    if st.button("▶️ Executar Query"):
        if custom_query:
            try:
                result_df = execute_custom_query(st.session_state.conn, custom_query)
                if not result_df.empty:
                    st.success(f"✅ Query executada com sucesso! {len(result_df)} registros retornados.")
                    st.dataframe(result_df, use_container_width=True, height=400)
                    
                    # Exportar resultado
                    query_csv = export_to_csv(result_df)
                    st.download_button(
                        "📥 Exportar Resultado da Query (CSV)",
                        query_csv,
                        "query_result.csv",
                        mime="text/csv"
                    )
            except Exception as e:
                st.error(f"❌ Erro ao executar query: {str(e)}")


def main():
    """Função principal da aplicação."""
    
    # Header
    st.markdown('<div class="main-header">🗄️ SQLite Viewer</div>', unsafe_allow_html=True)
    st.markdown("**Ferramenta interativa para análise e visualização de bancos SQLite**")
    
    # Inicializar estado da sessão
    initialize_session_state()
    
    # Renderizar sidebar
    render_connection_sidebar()
    
    # Verificar se há conexão ativa
    if st.session_state.conn is None:
        st.info("👈 Por favor, conecte-se a um banco SQLite usando a barra lateral.")
        return
    
    # Carregar tabelas
    try:
        tables = get_tables(st.session_state.conn, st.session_state.db_path)
        
        if not tables:
            st.warning("⚠️ Nenhuma tabela encontrada no banco de dados.")
            return
        
        # Sidebar - Seleção de tabela
        with st.sidebar:
            st.markdown("---")
            st.header("📋 Tabelas")
            selected_table = st.selectbox(
                "Selecione uma tabela",
                tables,
                help="Escolha a tabela que deseja analisar"
            )
        
        # Abas principais
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Explorador",
            "🔍 Análise de Duplicatas",
            "📈 Visualizações",
            "📉 Estatísticas",
            "🔎 Busca e Filtros"
        ])
        
        with tab1:
            render_explorer_tab(selected_table)
        
        with tab2:
            render_duplicates_tab(selected_table)
        
        with tab3:
            render_visualizations_tab(selected_table)
        
        with tab4:
            render_statistics_tab(selected_table)
        
        with tab5:
            render_search_tab(selected_table)
    
    except Exception as e:
        st.error(f"❌ Erro: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    main()

