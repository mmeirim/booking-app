import pandas as pd
from typing import List, Dict
import streamlit as st
from src.utils import sequence_generator

def calculate_end_hour(hora_inicio: str, hora_fim: str) -> str:
    """
    Calcula hora fim. Se vazia, adiciona 3 horas à hora início.
    Retorna string no formato HH:MM
    """
    if hora_fim and str(hora_fim).strip() and str(hora_fim) != 'nan':
        return str(hora_fim).strip()
    
    try:
        # Parse hora início
        h, m = map(int, hora_inicio.split(':'))
        
        # Adicionar 3 horas
        h_fim = (h + 3) % 24
        
        return f"{h_fim:02d}:{m:02d}"
    except:
        return "22:00"  # Fallback


def convert_to_minutes(horario: str) -> int:
    """Converte horário HH:MM para minutos desde meia-noite"""
    try:
        h, m = map(int, horario.split(':'))
        return h * 60 + m
    except:
        return 0


def verify_overbooking(h1_inicio: str, h1_fim: str, h2_inicio: str, h2_fim: str) -> bool:
    """
    Verifica se dois intervalos de horário se sobrepõem
    Retorna True se há sobreposição
    """
    inicio1 = convert_to_minutes(h1_inicio)
    fim1 = convert_to_minutes(h1_fim)
    inicio2 = convert_to_minutes(h2_inicio)
    fim2 = convert_to_minutes(h2_fim)
    
    # Não há sobreposição se um termina antes do outro começar
    return not (fim1 <= inicio2 or fim2 <= inicio1)

@st.cache_data
def find_conflicts(df_expandido: pd.DataFrame) -> List[Dict]:
    """
    Detecta conflitos de horário considerando TODAS as opções (Opção 1 e 2)
    Retorna lista de conflitos com detalhes
    """
    conflitos = []
    
    # 1. Pre-calculate end times and convert to proper datetime/time objects for fast comparison
    # Assuming calcular_hora_fim returns a string or object, convert to numeric/timedeltas if possible
    df = df_expandido.copy()
    df['Hora Fim Calculada'] = df.apply(
        lambda row: calculate_end_hour(row['Hora Início'], row['Hora fim']), axis=1
    )
    
    # 2. Group by Sala and Data. Only events in the same room on the same day can conflict.
    grouped = df.groupby(['Sala', 'Data Ocorrência'])
    
    for (sala, data), group in grouped:
        # If only one event in this room/day, no conflict possible
        if len(group) < 2:
            continue
            
        # 3. Sort by Start Time
        # This is the "Sweep" part: a conflict can only happen with events 
        # that start before the current one ends.
        sorted_group = group.sort_values('Hora Início').to_dict('records')
        
        for i in range(len(sorted_group)):
            for j in range(i + 1, len(sorted_group)):
                r1 = sorted_group[i]
                r2 = sorted_group[j]
                
                # Because it's sorted, if r2 starts AFTER r1 ends, 
                # then no subsequent r (r3, r4...) will conflict with r1 either.
                if r2['Hora Início'] >= r1['Hora Fim Calculada']:
                    break  # Optimization: Stop inner loop early
                
                # If we reach here, there is a conflict
                conflitos.append({
                    'id': sequence_generator.generate_id([sala, data, r1['id_reserva'], r2['id_reserva']]),
                    'sala': sala,
                    'data': data,
                    'dia_semana': r1['Dia da semana'],
                    'id_reserva1': r1['id_reserva'],
                    'grupo1': r1['Grupo'],
                    'atividade1': r1['Atividade'],
                    'horario1': f"{r1['Hora Início']}-{r1['Hora Fim Calculada']}",
                    'responsavel1': r1['Responsável'],
                    'status1': r1['Status'],
                    'id_reserva2': r2['id_reserva'],
                    'grupo2': r2['Grupo'],
                    'atividade2': r2['Atividade'],
                    'horario2': f"{r2['Hora Início']}-{r2['Hora Fim Calculada']}",
                    'responsavel2': r2['Responsável'],
                    'status2': r2['Status'],
                })

    return conflitos

