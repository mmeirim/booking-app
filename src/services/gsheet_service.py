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

