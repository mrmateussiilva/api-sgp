"""
Módulo para gerenciamento de conexões e operações com banco SQLite.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from typing import List, Optional, Tuple
import streamlit as st


@st.cache_data
def validate_sqlite_file(file_path: str) -> bool:
    """
    Valida se um arquivo é um banco SQLite válido.
    
    Args:
        file_path: Caminho do arquivo
        
    Returns:
        True se for um arquivo SQLite válido
    """
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        cursor.close()
        conn.close()
        return True
    except Exception:
        return False


@st.cache_data
def get_tables(_conn: sqlite3.Connection, db_path: str) -> List[str]:
    """
    Obtém lista de todas as tabelas do banco.
    
    Args:
        _conn: Conexão SQLite (ignorado no cache)
        db_path: Caminho do arquivo do banco (usado como chave de cache)
        
    Returns:
        Lista de nomes de tabelas
    """
    cursor = _conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables


@st.cache_data
def get_table_info(_conn: sqlite3.Connection, db_path: str, table_name: str) -> pd.DataFrame:
    """
    Obtém informações sobre colunas de uma tabela.
    
    Args:
        _conn: Conexão SQLite (ignorado no cache)
        db_path: Caminho do arquivo do banco (usado como chave de cache)
        table_name: Nome da tabela
        
    Returns:
        DataFrame com informações das colunas
    """
    cursor = _conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    cursor.close()
    
    df_info = pd.DataFrame(
        columns,
        columns=['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk']
    )
    return df_info


@st.cache_data
def get_table_data(_conn: sqlite3.Connection, db_path: str, table_name: str, limit: Optional[int] = None) -> pd.DataFrame:
    """
    Obtém dados de uma tabela.
    
    Args:
        _conn: Conexão SQLite (ignorado no cache)
        db_path: Caminho do arquivo do banco (usado como chave de cache)
        table_name: Nome da tabela
        limit: Limite de linhas (None para todas)
        
    Returns:
        DataFrame com os dados
    """
    query = f"SELECT * FROM {table_name}"
    if limit:
        query += f" LIMIT {limit}"
    
    df = pd.read_sql_query(query, _conn)
    return df


@st.cache_data
def get_row_count(_conn: sqlite3.Connection, db_path: str, table_name: str) -> int:
    """
    Obtém número total de registros em uma tabela.
    
    Args:
        _conn: Conexão SQLite (ignorado no cache)
        db_path: Caminho do arquivo do banco (usado como chave de cache)
        table_name: Nome da tabela
        
    Returns:
        Número de registros
    """
    cursor = _conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    count = cursor.fetchone()[0]
    cursor.close()
    return count


def execute_custom_query(conn: sqlite3.Connection, query: str) -> pd.DataFrame:
    """
    Executa uma query SQL customizada.
    
    Args:
        conn: Conexão SQLite
        query: Query SQL
        
    Returns:
        DataFrame com resultados
    """
    try:
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        raise ValueError(f"Erro ao executar query: {str(e)}")


def get_database_size(db_path: str) -> float:
    """
    Obtém o tamanho do arquivo do banco em MB.
    
    Args:
        db_path: Caminho do arquivo do banco
        
    Returns:
        Tamanho em MB
    """
    return Path(db_path).stat().st_size / (1024 * 1024)

