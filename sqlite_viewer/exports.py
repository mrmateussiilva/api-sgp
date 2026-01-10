"""
Módulo para exportação de dados.
"""

import pandas as pd
from io import BytesIO
from typing import Optional


def export_to_csv(df: pd.DataFrame) -> bytes:
    """
    Exporta DataFrame para CSV.
    
    Args:
        df: DataFrame para exportar
        
    Returns:
        Bytes do arquivo CSV
    """
    return df.to_csv(index=False).encode('utf-8')


def export_to_excel(df: pd.DataFrame, sheet_name: str = 'Dados') -> bytes:
    """
    Exporta DataFrame para Excel.
    
    Args:
        df: DataFrame para exportar
        sheet_name: Nome da planilha
        
    Returns:
        Bytes do arquivo Excel
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()


def export_multiple_to_excel(dataframes: dict) -> bytes:
    """
    Exporta múltiplos DataFrames para um único arquivo Excel.
    
    Args:
        dataframes: Dicionário {nome_planilha: DataFrame}
        
    Returns:
        Bytes do arquivo Excel
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for sheet_name, df in dataframes.items():
            df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()

