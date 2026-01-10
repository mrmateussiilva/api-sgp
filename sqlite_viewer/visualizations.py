"""
Módulo para criação de visualizações e gráficos.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Optional


def create_null_heatmap(df: pd.DataFrame) -> go.Figure:
    """
    Cria heatmap de valores nulos.
    
    Args:
        df: DataFrame para análise
        
    Returns:
        Figura Plotly
    """
    null_counts = df.isnull().sum()
    null_percentages = (null_counts / len(df)) * 100
    
    fig = go.Figure(data=go.Heatmap(
        z=[null_percentages.values],
        x=null_percentages.index,
        y=['Valores Nulos (%)'],
        colorscale='Reds',
        showscale=True,
        text=[[f'{val:.1f}%' for val in null_percentages.values]],
        texttemplate='%{text}',
        textfont={"size": 10}
    ))
    
    fig.update_layout(
        title='Mapa de Calor - Valores Nulos por Coluna',
        height=300,
        xaxis_title='Colunas',
        yaxis_title=''
    )
    
    return fig


def create_histogram(df: pd.DataFrame, column: str, nbins: int = 30) -> go.Figure:
    """
    Cria histograma para coluna numérica.
    
    Args:
        df: DataFrame
        column: Nome da coluna numérica
        nbins: Número de bins
        
    Returns:
        Figura Plotly
    """
    fig = px.histogram(
        df,
        x=column,
        title=f"Distribuição - {column}",
        nbins=nbins
    )
    return fig


def create_box_plot(df: pd.DataFrame, column: str) -> go.Figure:
    """
    Cria box plot para coluna numérica.
    
    Args:
        df: DataFrame
        column: Nome da coluna numérica
        
    Returns:
        Figura Plotly
    """
    fig = px.box(
        df,
        y=column,
        title=f"Box Plot - {column}"
    )
    return fig


def create_pie_chart(value_counts: pd.Series, title: str) -> go.Figure:
    """
    Cria gráfico de pizza.
    
    Args:
        value_counts: Série com valores e contagens
        title: Título do gráfico
        
    Returns:
        Figura Plotly
    """
    fig = px.pie(
        values=value_counts.values,
        names=value_counts.index,
        title=title
    )
    return fig


def create_bar_chart(x_values: List, y_values: List, x_label: str, y_label: str, title: str) -> go.Figure:
    """
    Cria gráfico de barras.
    
    Args:
        x_values: Valores do eixo X
        y_values: Valores do eixo Y
        x_label: Rótulo do eixo X
        y_label: Rótulo do eixo Y
        title: Título do gráfico
        
    Returns:
        Figura Plotly
    """
    fig = px.bar(
        x=x_values,
        y=y_values,
        title=title,
        labels={'x': x_label, 'y': y_label}
    )
    fig.update_xaxes(tickangle=45)
    return fig


def create_line_chart(df: pd.DataFrame, x_column: str, y_column: str, title: str) -> go.Figure:
    """
    Cria gráfico de linha.
    
    Args:
        df: DataFrame
        x_column: Nome da coluna X
        y_column: Nome da coluna Y
        title: Título do gráfico
        
    Returns:
        Figura Plotly
    """
    fig = px.line(
        df,
        x=x_column,
        y=y_column,
        title=title,
        markers=True
    )
    return fig


def create_time_series(df: pd.DataFrame, date_column: str) -> go.Figure:
    """
    Cria gráfico de série temporal.
    
    Args:
        df: DataFrame
        date_column: Nome da coluna de data
        
    Returns:
        Figura Plotly
    """
    df_copy = df.copy()
    df_copy[date_column] = pd.to_datetime(df_copy[date_column])
    df_date = df_copy.groupby(df_copy[date_column].dt.date).size().reset_index(name='contagem')
    
    fig = px.line(
        df_date,
        x=date_column,
        y='contagem',
        title=f"Tendência Temporal - {date_column}",
        markers=True
    )
    return fig


def create_duplicates_bar_chart(duplicates_df: pd.DataFrame, column_name: str) -> go.Figure:
    """
    Cria gráfico de barras para valores duplicados.
    
    Args:
        duplicates_df: DataFrame com valores duplicados
        column_name: Nome da coluna analisada
        
    Returns:
        Figura Plotly
    """
    top_10 = duplicates_df.head(10)
    fig = px.bar(
        top_10,
        x='valor',
        y='contagem',
        labels={'valor': 'Valor', 'contagem': 'Contagem'},
        title=f"Top 10 Valores Duplicados - {column_name}"
    )
    fig.update_xaxes(tickangle=45)
    return fig

