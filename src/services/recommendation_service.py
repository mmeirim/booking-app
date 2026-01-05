import pandas as pd
from typing import List, Dict
from datetime import datetime, timedelta

import streamlit as st
import app as app

@st.cache_data
def generate_recommendations(df_expandido: pd.DataFrame, df_salas: pd.DataFrame, 
                    df_grupos: pd.DataFrame, conflitos: List[Dict]) -> List[Dict]:
    """
    Gera sugestões de melhor opção de sala quando há múltiplas opções
    """
    sugestoes = []
    
    # Garantir que a capacidade em df_salas seja numérica
    df_salas['Capacidade'] = pd.to_numeric(df_salas['Capacidade'], errors='coerce').fillna(0)

    for conf in conflitos:
        data = conf['data']
        h_inicio_g1 = conf['horario1'].split("-")[0]
        h_fim_g1 = conf['horario1'].split("-")[1]
        h_inicio_g2 = conf['horario2'].split("-")[0]
        h_fim_g2 = conf['horario2'].split("-")[1]
        
        # 1. Obter a capacidade da sala original
        cap_original = 0
        info_sala_orig = df_salas[df_salas['Sala'] == conf['sala']]
        if not info_sala_orig.empty:
            cap_original = info_sala_orig.iloc[0]['Capacidade']
            
        participantes_g1 = 0
        participantes_g2 = 0
        if not df_grupos.empty:
            info_g1 = df_grupos[df_grupos['Grupo'] == conf['grupo1']]
            info_g2 = df_grupos[df_grupos['Grupo'] == conf['grupo2']]
            if not info_g1.empty and not info_g2.empty:
                participantes_g1 = pd.to_numeric(info_g1.iloc[0]['# Participantes'], errors='coerce') or 0
                participantes_g2 = pd.to_numeric(info_g2.iloc[0]['# Participantes'], errors='coerce') or 0
            
        # 2. Calcular o limite mínimo aceitável (Tolerância)
        # Regra: ref = Mínimo entre Capacidade da Sala e Número de Participantes
        # Máximo entre (Ref - 10%) ou (Ref - 5)
        ref_g1 = min(cap_original, participantes_g1) if participantes_g1 > 0 else cap_original
        limite_minimo_g1 = max(ref_g1 * 0.9, ref_g1 - 5)
        
        ref_g2 = min(cap_original, participantes_g2) if participantes_g2 > 0 else cap_original
        limite_minimo_g2 = max(ref_g2 * 0.9, ref_g2 - 5)

        # 3. Buscar salas fisicamente disponíveis no horário
        salas_livres_g1 = search_available_rooms(df_expandido, df_salas, data, h_inicio_g1, h_fim_g1)
        salas_livres_g2 = search_available_rooms(df_expandido, df_salas, data, h_inicio_g2, h_fim_g2)
        
        # 4. Filtrar salas livres que suportam o número de participantes
        sugestoes_salas_g1 = set()
        sugestoes_salas_g2 = set()
        if not df_salas.empty:
            sugestoes_salas_g1 = analyze_relocation(
                df_salas, salas_livres_g1, cap_original, limite_minimo_g1)
           
            sugestoes_salas_g2 = analyze_relocation(
                    df_salas, salas_livres_g2, cap_original, limite_minimo_g2)

        # 5. Cálculo de Duração do Conflito para ajuste de tempo
        # Transformamos em datetime para calcular a diferença
        duracao_conflito_min = analyze_short_conflict(h_inicio_g1, h_fim_g1, h_inicio_g2, h_fim_g2)

        ajuste_horario = ""
        if 0 < duracao_conflito_min <= 30:
            ajuste_horario = f"⏱️ Conflito curto ({int(duracao_conflito_min)}min). Sugestão: Ajustar o horário em 30 min para liberar a sala."

        # 6. Consolidar Sugestão
        sugestao = {
            'id_conflito': conf.get('id'),
            'sala_original': conf['sala'], # Essencial para o filtro por sala
            'data': data,
            'grupo1': conf['grupo1'],     # Grupo da esquerda
            'grupo2': conf['grupo2'],     # Grupo da direita
            'atividade': conf['atividade1'], # Ou concatenar ambas
            'responsavel': conf['responsavel1'],
            'salas_recomendadas_g1': sugestoes_salas_g1[:5],
            'salas_recomendadas_g2': sugestoes_salas_g2[:5],
            'outras_salas_livres_g1': set(salas_livres_g1) - set(sugestoes_salas_g1[:5]),
            'outras_salas_livres_g2': set(salas_livres_g2) - set(sugestoes_salas_g2[:5]),
            'ajuste_tempo': ajuste_horario,
            'justificativa': f"Sala original: {cap_original} pessoas. Sugerindo salas com capacidade mais próxima da necessidade dos grupos.",
            'resolvido': len(sugestoes_salas_g1) > 0 or len(sugestoes_salas_g2) > 0 or ajuste_horario != ""
        }
        
        sugestoes.append(sugestao)
        
    return sugestoes

def analyze_relocation(df_salas: pd.DataFrame, salas_livres_nomes: List[str], 
                       cap_original: int, limite_minimo: int) -> List[str]:
     # Filtro: Está livre E Capacidade >= limite_minimo
    condicao = (df_salas['Sala'].isin(salas_livres_nomes)) & (df_salas['Capacidade'] >= limite_minimo)
    
    # Ordenação: Queremos as mais próximas da original primeiro. 
    # Calculamos a diferença absoluta para ordenar
    salas_possiveis = df_salas[condicao].copy()
    salas_possiveis['diff'] = (salas_possiveis['Capacidade'] - cap_original).abs()
    
    # Ordenamos pela menor diferença absoluta, priorizando as maiores em caso de empate
    sugestoes_salas_df = salas_possiveis.sort_values(by=['diff', 'Capacidade'], ascending=[True, False])
    return sugestoes_salas_df['Sala'].tolist()

def analyze_short_conflict(h_inicio_g1: str, h_fim_g1: str, 
                           h_inicio_g2: str, h_fim_g2: str) -> float:
    fmt = '%H:%M'
    ti_g1 = datetime.strptime(h_inicio_g1, fmt)
    tf_g1 = datetime.strptime(h_fim_g1, fmt)
    ti_g2 = datetime.strptime(h_inicio_g2, fmt)
    tf_g2 = datetime.strptime(h_fim_g2, fmt)

    # O conflito começa no horário mais tardio de início
    inicio_conflito = max(ti_g1, ti_g2)
    # O conflito termina no horário mais cedo de término
    fim_conflito = min(tf_g1, tf_g2)

    # A duração é a diferença entre esses dois pontos
    if fim_conflito > inicio_conflito:
        duracao_conflito_min = (fim_conflito - inicio_conflito).total_seconds() / 60
    else:
        duracao_conflito_min = 0
        
    return duracao_conflito_min

@st.cache_data
def search_available_rooms(df_expandido, df_salas, data, hora_inicio, hora_fim):
    """Retorna lista de salas sem reservas que sobreponham o horário informado."""
    # Converter para comparação numérica/time para evitar erros de string
    fmt = '%H:%M'
    h_ini_query = datetime.strptime(hora_inicio, fmt).time()
    h_fim_query = datetime.strptime(hora_fim, fmt).time()
    
    # Filtrar apenas o dia em questão
    reservas_dia = df_expandido[df_expandido['Data Ocorrência'] == data].copy()
    
    # Identificar salas ocupadas por sobreposição: (Ini1 < Fim2) AND (Fim1 > Ini2)
    ocupadas = []
    for _, res in reservas_dia.iterrows():
        res_ini = datetime.strptime(res['Hora Início'], fmt).time()
        res_fim = datetime.strptime(res['Hora fim'], fmt).time()
        
        if h_ini_query < res_fim and h_fim_query > res_ini:
            ocupadas.append(res['Sala'])
            
    todas_salas = set(df_salas['Sala'].unique())
    salas_livres = todas_salas - set(ocupadas)
    
    return sorted(list(salas_livres))