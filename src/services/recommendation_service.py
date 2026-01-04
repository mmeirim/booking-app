import pandas as pd
from typing import List, Dict
import streamlit as st
import app as app

def generate_recommendations(df_original: pd.DataFrame, conflitos: List[Dict]) -> List[Dict]:
    """
    Gera sugestões de melhor opção de sala quando há múltiplas opções
    """
    sugestoes = []
    
    # Agrupar por Grupo + Atividade + Data Início
    grupos = df_original.groupby(['Grupo', 'Atividade', 'Data Início'])
    
    for (grupo, atividade, data), opcoes_df in grupos:
        opcoes = opcoes_df.to_dict('records')
        
        # Se tem apenas 1 opção, usar essa
        if len(opcoes) == 1:
            sugestao = {
                'grupo': grupo,
                'atividade': atividade,
                'data': data,
                'opcoes_disponiveis': f"{opcoes[0]['Sala']} ({opcoes[0]['Status']})",
                'sala_recomendada': opcoes[0]['Sala'],
                'justificativa': 'Única opção disponível',
                'conflitos': 0,
                'responsavel': opcoes[0]['Responsável']
            }
            sugestoes.append(sugestao)
            continue
        
        # Se tem múltiplas opções, analisar conflitos
        opcao1 = next((o for o in opcoes if o['Status'] == 'Opção 1'), None)
        opcao2 = next((o for o in opcoes if o['Status'] == 'Opção 2'), None)
        
        if not opcao1 and not opcao2:
            continue
        
        # Contar conflitos para cada opção
        conflitos_opcao1 = len([
            c for c in conflitos 
            if opcao1 and c['sala'] == opcao1['Sala'] and c['data'] == data
        ]) if opcao1 else 999
        
        conflitos_opcao2 = len([
            c for c in conflitos 
            if opcao2 and c['sala'] == opcao2['Sala'] and c['data'] == data
        ]) if opcao2 else 999
        
        # Decidir melhor opção
        opcoes_str = []
        if opcao1:
            opcoes_str.append(f"{opcao1['Sala']} (Opção 1)")
        if opcao2:
            opcoes_str.append(f"{opcao2['Sala']} (Opção 2)")
        
        if conflitos_opcao1 == 0 and conflitos_opcao2 == 0:
            sala_recomendada = opcao1['Sala'] if opcao1 else opcao2['Sala']
            justificativa = 'Ambas livres - Opção 1 como padrão'
            conflitos_total = 0
        elif conflitos_opcao1 == 0:
            sala_recomendada = opcao1['Sala']
            justificativa = 'Opção 1 sem conflitos'
            conflitos_total = 0
        elif conflitos_opcao2 == 0:
            sala_recomendada = opcao2['Sala']
            justificativa = 'Opção 2 sem conflitos'
            conflitos_total = 0
        elif conflitos_opcao1 < conflitos_opcao2:
            sala_recomendada = opcao1['Sala'] if opcao1 else opcao2['Sala']
            justificativa = f'Menos conflitos ({conflitos_opcao1} vs {conflitos_opcao2})'
            conflitos_total = conflitos_opcao1
        else:
            sala_recomendada = opcao2['Sala'] if opcao2 else opcao1['Sala']
            justificativa = f'Menos conflitos ({conflitos_opcao2} vs {conflitos_opcao1})'
            conflitos_total = conflitos_opcao2
        
        sugestao = {
            'grupo': grupo,
            'atividade': atividade,
            'data': data,
            'opcoes_disponiveis': ' ou '.join(opcoes_str),
            'sala_recomendada': sala_recomendada,
            'justificativa': justificativa,
            'conflitos': conflitos_total,
            'responsavel': opcoes[0]['Responsável']
        }
        sugestoes.append(sugestao)
    
    return sugestoes

@st.cache_data
def search_available_rooms(df_expandido, data, hora_inicio, hora_fim):
    """Retorna lista de salas que não têm reservas no período informado"""
    df = df_expandido.copy()
    df['Hora Fim Calculada'] = df.apply(
        lambda row: app.calcular_hora_fim(row['Hora Início'], row['Hora fim']), axis=1
    )
    
    todas_salas = set(df['Sala'].unique())
    
    # Filtrar reservas no mesmo dia
    reservas_dia = df[df['Data Ocorrência'] == data]
    
    salas_ocupadas = set()
    for _, res in reservas_dia.iterrows():
        # Lógica de sobreposição: (Início1 < Fim2) e (Fim1 > Início2)
        if (hora_inicio < res['Hora Fim Calculada']) and (hora_fim > res['Hora Início']):
            salas_ocupadas.add(res['Sala'])
    
    salas_livres = todas_salas - salas_ocupadas
    return sorted(list(salas_livres))