import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import src.utils.sequence_generator as sequence_generator

@st.cache_data
def expand_recurring_events(df: pd.DataFrame) -> pd.DataFrame:
    ocorrencias_expandidas = []
    
    for idx, row in df.iterrows():
        recorrencia = str(row['Recorrência']).strip() if pd.notna(row['Recorrência']) else ''
        
        # Se não tem recorrência, é única
        if not recorrencia or recorrencia == 'nan' or recorrencia == '':
            row_copy = row.copy()
            row_copy['Data Ocorrência'] = row['Data Início']
            ocorrencias_expandidas.append(row_copy)
            continue
        
        # Expandir baseado no tipo de recorrência
        try:
            data_inicio = pd.to_datetime(row['Data Início'], dayfirst=True)
            data_fim = datetime(2026, 12, 31)
            
            partes = recorrencia.split('-')
            tipo = partes[0]
            
            if tipo == 'Semanal' and len(partes) >= 2:
                # Semanal-Segunda, Semanal-Terça, etc
                data_atual = data_inicio
                while data_atual <= data_fim:
                    row_copy = row.copy()
                    row_copy['Data Ocorrência'] = data_atual.strftime('%d/%m/%Y')
                    ocorrencias_expandidas.append(row_copy)
                    data_atual += timedelta(days=7)
            
            elif tipo == 'Quinzenal' and len(partes) >= 2:
                # Quinzenal-Quarta, etc
                data_atual = data_inicio
                while data_atual <= data_fim:
                    row_copy = row.copy()
                    row_copy['Data Ocorrência'] = data_atual.strftime('%d/%m/%Y')
                    ocorrencias_expandidas.append(row_copy)
                    data_atual += timedelta(days=14)
            
            elif tipo == 'Mensal' and len(partes) >= 3:
                # Mensal-2º-Domingo, Mensal-1º-Segunda, etc
                ordem = int(partes[1].replace('º', ''))
                dia_semana_nome = partes[2]
                
                dias_semana = {
                    'Domingo': 0, 'Segunda': 1, 'Terça': 2, 'Quarta': 3,
                    'Quinta': 4, 'Sexta': 5, 'Sábado': 6
                }
                dia_semana_alvo = dias_semana.get(dia_semana_nome, 0)
                
                for mes in range(1, 13):
                    contador = 0
                    for dia in range(1, 32):
                        try:
                            data_teste = datetime(2026, mes, dia)
                            if data_teste.weekday() == (dia_semana_alvo - 1) % 7:
                                contador += 1
                                if contador == ordem:
                                    row_copy = row.copy()
                                    row_copy['Data Ocorrência'] = data_teste.strftime('%d/%m/%Y')
                                    ocorrencias_expandidas.append(row_copy)
                                    break
                        except ValueError:
                            break
            
            else:
                # Recorrência não reconhecida, trata como única
                row_copy = row.copy()
                row_copy['Data Ocorrência'] = row['Data Início']
                ocorrencias_expandidas.append(row_copy)
        
        except Exception as e:
            st.warning(f"⚠️ Erro ao expandir recorrência na linha {idx}: {str(e)}")
            row_copy = row.copy()
            row_copy['Data Ocorrência'] = row['Data Início']
            ocorrencias_expandidas.append(row_copy)
    
    df_expandido = pd.DataFrame(ocorrencias_expandidas)
    df_expandido['id_reserva'] = df_expandido.apply(
            lambda row: sequence_generator.generate_id([row['Grupo'], row['Sala'], row['Data Ocorrência'], 
                                                        row['Hora Início']]), axis=1)
    
    return df_expandido
