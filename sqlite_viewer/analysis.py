"""
Módulo para análise de duplicatas e estatísticas.
"""

import pandas as pd
from typing import List, Tuple


def get_duplicate_rows(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """
    Encontra linhas completamente duplicadas.
    
    Args:
        df: DataFrame para análise
        
    Returns:
        Tupla com (DataFrame de duplicatas, número de duplicatas)
    """
    duplicates = df[df.duplicated(keep=False)]
    return duplicates, len(duplicates)


def get_duplicate_values_by_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Encontra valores duplicados em uma coluna específica.
    
    Args:
        df: DataFrame para análise
        column: Nome da coluna
        
    Returns:
        DataFrame com valores duplicados e suas contagens
    """
    value_counts = df[column].value_counts()
    duplicates = value_counts[value_counts > 1].reset_index()
    duplicates.columns = ['valor', 'contagem']
    return duplicates.sort_values('contagem', ascending=False)


def get_duplicate_combinations(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """
    Encontra combinações duplicadas de colunas.
    
    Args:
        df: DataFrame para análise
        columns: Lista de nomes de colunas
        
    Returns:
        DataFrame com combinações duplicadas
    """
    grouped = df.groupby(columns).size().reset_index(name='contagem')
    duplicates = grouped[grouped['contagem'] > 1].sort_values('contagem', ascending=False)
    return duplicates


def get_statistical_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Obtém resumo estatístico de colunas numéricas.
    
    Args:
        df: DataFrame para análise
        
    Returns:
        DataFrame com estatísticas descritivas
    """
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if numeric_cols:
        return df[numeric_cols].describe()
    return pd.DataFrame()


def get_null_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Obtém estatísticas de valores nulos por coluna.
    
    Args:
        df: DataFrame para análise
        
    Returns:
        DataFrame com contagem e percentual de nulos
    """
    null_counts = df.isnull().sum()
    null_df = pd.DataFrame({
        'Coluna': null_counts.index,
        'Valores Nulos': null_counts.values,
        'Percentual (%)': (null_counts.values / len(df) * 100).round(2)
    }).sort_values('Valores Nulos', ascending=False)
    return null_df


def get_data_types_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Obtém distribuição de tipos de dados.
    
    Args:
        df: DataFrame para análise
        
    Returns:
        DataFrame com tipos e quantidades
    """
    type_counts = df.dtypes.value_counts()
    type_df = pd.DataFrame({
        'Tipo': type_counts.index.astype(str),
        'Quantidade': type_counts.values
    })
    return type_df


def filter_dataframe(df: pd.DataFrame, column: str, operator: str, value: str):
    """
    Filtra DataFrame baseado em coluna, operador e valor.
    
    Args:
        df: DataFrame para filtrar
        column: Nome da coluna
        operator: Operador (=, !=, >, <, >=, <=, LIKE, NOT LIKE)
        value: Valor para comparar
        
    Returns:
        DataFrame filtrado
    """
    if operator == "=":
        return df[df[column] == value]
    elif operator == "!=":
        return df[df[column] != value]
    elif operator == ">":
        return df[df[column] > value]
    elif operator == "<":
        return df[df[column] < value]
    elif operator == ">=":
        return df[df[column] >= value]
    elif operator == "<=":
        return df[df[column] <= value]
    elif operator == "LIKE":
        return df[df[column].astype(str).str.contains(value, case=False, na=False)]
    elif operator == "NOT LIKE":
        return df[~df[column].astype(str).str.contains(value, case=False, na=False)]
    else:
        return df


def search_in_dataframe(df: pd.DataFrame, search_term: str) -> pd.DataFrame:
    """
    Busca termo em todas as colunas do DataFrame.
    
    Args:
        df: DataFrame para buscar
        search_term: Termo de busca
        
    Returns:
        DataFrame filtrado com resultados
    """
    mask = df.astype(str).apply(
        lambda x: x.str.contains(search_term, case=False, na=False)
    ).any(axis=1)
    return df[mask]


def detect_date_columns(df: pd.DataFrame) -> List[str]:
    """
    Detecta colunas que podem ser datas.
    
    Args:
        df: DataFrame para análise
        
    Returns:
        Lista de nomes de colunas que são datas
    """
    date_cols = []
    
    # Colunas já do tipo datetime
    for col in df.columns:
        if df[col].dtype == 'datetime64[ns]':
            date_cols.append(col)
    
    # Tentar detectar por nome
    for col in df.columns:
        if col not in date_cols and ('date' in col.lower() or 'data' in col.lower()):
            try:
                pd.to_datetime(df[col])
                date_cols.append(col)
            except:
                pass
    
    return date_cols

