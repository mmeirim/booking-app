import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

@st.cache_data
def conn_gsheets(spreadsheet_id: str, worksheet_name: str = "Reservas") -> pd.DataFrame:
    try:
        # Configurar credenciais
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Usar secrets do Streamlit
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Abrir planilha
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.worksheet(worksheet_name)
        
        # Obter todos os dados
        data = worksheet.get_all_records()
        
        # Converter para DataFrame
        dtype_spec = {
            'Sala': str,   
            'Dia da semana': str,
            'Data Início': str,
            'Hora Início': str,
            'Hora fim': str,
            'Recorrência': str,
            'Grupo': str,
            'Atividade': str,
            'Responsável': str,
            'Status': str
        }

        df = pd.DataFrame(data)
        df = df.astype(dtype_spec)
        
        # Validar colunas essenciais
        colunas_esperadas = [
            'Sala', 'Dia da semana', 'Data Início', 'Hora Início', 
            'Hora fim', 'Recorrência', 'Grupo', 'Atividade', 
            'Responsável', 'Status'
        ]
        
        colunas_faltantes = set(colunas_esperadas) - set(df.columns)
        if colunas_faltantes:
            st.error(f"❌ Colunas faltantes no Google Sheet: {colunas_faltantes}")
            return pd.DataFrame()
        
        print("Original dtypes:\n", df.dtypes)

        return df
    
    except Exception as e:
        st.error(f"❌ Erro ao conectar com Google Sheets: {str(e)}")
        st.info("💡 Verifique se as credenciais estão configuradas corretamente em secrets.toml")
        return pd.DataFrame()

def process_worksheet(worksheet, ex_columns) -> pd.DataFrame:
    data = worksheet.get_all_records()
    if not data: 
        return pd.DataFrame(columns=ex_columns)
    
    df = pd.DataFrame(data)
    
    # Validação rápida de colunas
    faltantes = set(ex_columns) - set(df.columns)
    if faltantes:
        st.error(f"❌ Colunas faltantes na aba '{worksheet.title}': {faltantes}")
        return pd.DataFrame()
    
    # Seleciona as colunas e converte tudo para string de uma vez (.astype(str))
    return df[ex_columns].astype(str)

@st.cache_data
def load_all_data_gsheets(spreadsheet_id: str):
    try:
        # 1. Autenticação (Apenas uma vez)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # 2. Abrir a Planilha (Apenas uma vez)
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # 3. Chamadas das funções específicas passando o objeto spreadsheet
        # Isso evita re-conectar à API para cada aba
        dict_dataframes = {}
        
        try:
            dict_dataframes['Reservas'] = process_worksheet(spreadsheet.worksheet("Reservas"),
                                                                 ['Sala', 'Dia da semana', 'Data Início', 'Hora Início', 
                                                                  'Hora fim', 'Recorrência', 'Grupo', 'Atividade','Responsável',
                                                                  'Status'])
            dict_dataframes['Salas'] = process_worksheet(spreadsheet.worksheet("Salas"), ['Sala', 'Capacidade'])
            dict_dataframes['Grupos'] = process_worksheet(spreadsheet.worksheet("Controle de Pastorais"), ['Grupo', '# Participantes'])

            # Adicione outras conforme necessário
        except gspread.WorksheetNotFound as e:
            st.warning(f"⚠️ Uma das abas não foi encontrada: {str(e)}")

        return dict_dataframes
    
    except Exception as e:
        st.error(f"❌ Erro na conexão principal: {str(e)}")
        return {}
