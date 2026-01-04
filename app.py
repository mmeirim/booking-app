import streamlit as st
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json
from typing import List, Dict, Tuple
import plotly.express as px
import plotly.graph_objects as go
import src.services.gsheet_service as gsheet_service
import src.services.recommendation_service as recommendation_service

# ============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================================

st.set_page_config(
    page_title="Sistema de Reservas de Salas 2026",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def validar_estrutura_dados(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Valida se os dados do Google Sheets estão no formato correto"""
    erros = []
    
    if df.empty:
        erros.append("DataFrame vazio")
        return False, erros
    
    # Validar datas
    try:
        pd.to_datetime(df['Data Início'], dayfirst=True, errors='coerce')
    except:
        erros.append("Formato de data inválido em 'Data Início' (use YYYY-MM-DD)")
    
    # Validar horários
    for col in ['Hora Início', 'Hora fim']:
        if col in df.columns:
            valores_nao_vazios = df[df[col].notna()][col]
            for hora in valores_nao_vazios:
                if hora and not pd.isna(hora):
                    if ':' not in str(hora):
                        erros.append(f"Formato de horário inválido em '{col}' (use HH:MM)")
                        break
    
    return len(erros) == 0, erros


# ============================================================================
# FASE 4.2: CÁLCULO DE HORÁRIOS
# ============================================================================

def calcular_hora_fim(hora_inicio: str, hora_fim: str) -> str:
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


def horario_para_minutos(horario: str) -> int:
    """Converte horário HH:MM para minutos desde meia-noite"""
    try:
        h, m = map(int, horario.split(':'))
        return h * 60 + m
    except:
        return 0


def verificar_sobreposicao(h1_inicio: str, h1_fim: str, h2_inicio: str, h2_fim: str) -> bool:
    """
    Verifica se dois intervalos de horário se sobrepõem
    Retorna True se há sobreposição
    """
    inicio1 = horario_para_minutos(h1_inicio)
    fim1 = horario_para_minutos(h1_fim)
    inicio2 = horario_para_minutos(h2_inicio)
    fim2 = horario_para_minutos(h2_fim)
    
    # Não há sobreposição se um termina antes do outro começar
    return not (fim1 <= inicio2 or fim2 <= inicio1)


# ============================================================================
# FASE 4.1: EXPANSÃO DE RECORRÊNCIAS
# ============================================================================
@st.cache_data
def expandir_recorrencias(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expande todas as recorrências para gerar lista completa de ocorrências em 2026
    """
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
    
    return pd.DataFrame(ocorrencias_expandidas)


# ============================================================================
# FASE 4.3: DETECÇÃO DE CONFLITOS
# ============================================================================
@st.cache_data
def detectar_conflitos(df_expandido: pd.DataFrame) -> List[Dict]:
    """
    Detecta conflitos de horário considerando TODAS as opções (Opção 1 e 2)
    Retorna lista de conflitos com detalhes
    """
    conflitos = []
    
    # 1. Pre-calculate end times and convert to proper datetime/time objects for fast comparison
    # Assuming calcular_hora_fim returns a string or object, convert to numeric/timedeltas if possible
    df = df_expandido.copy()
    df['Hora Fim Calculada'] = df.apply(
        lambda row: calcular_hora_fim(row['Hora Início'], row['Hora fim']), axis=1
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
                    'sala': sala,
                    'data': data,
                    'grupo1': r1['Grupo'],
                    'atividade1': r1['Atividade'],
                    'horario1': f"{r1['Hora Início']}-{r1['Hora Fim Calculada']}",
                    'responsavel1': r1['Responsável'],
                    'status1': r1['Status'],
                    'grupo2': r2['Grupo'],
                    'atividade2': r2['Atividade'],
                    'horario2': f"{r2['Hora Início']}-{r2['Hora Fim Calculada']}",
                    'responsavel2': r2['Responsável'],
                    'status2': r2['Status'],
                })
                
    return conflitos

# ============================================================================
# ESTATÍSTICAS E ANÁLISES
# ============================================================================

def calcular_estatisticas(df_reservas: pd.DataFrame, df_expandido: pd.DataFrame, 
                         conflitos: List[Dict], sugestoes: List[Dict]) -> Dict:
    """Calcula estatísticas gerais do sistema"""
    
    salas = df_reservas['Sala'].unique()
    grupos = df_reservas['Grupo'].unique()
    
    # Conflitos por sala
    conflitos_por_sala = {}
    for c in conflitos:
        sala = c['sala']
        conflitos_por_sala[sala] = conflitos_por_sala.get(sala, 0) + 1
    
    sala_mais_conflitos = max(conflitos_por_sala.items(), key=lambda x: x[1]) if conflitos_por_sala else ('Nenhuma', 0)
    
    # Percentual sem conflito
    sugestoes_sem_conflito = len([s for s in sugestoes if s['conflitos'] == 0])
    percentual_sem_conflito = (sugestoes_sem_conflito / len(sugestoes) * 100) if sugestoes else 100
    
    return {
        'total_reservas_originais': len(df_reservas),
        'total_ocorrencias': len(df_expandido),
        'total_conflitos': len(conflitos),
        'total_salas': len(salas),
        'total_grupos': len(grupos),
        'atividades_com_opcoes': len(sugestoes),
        'sala_mais_conflitos': sala_mais_conflitos,
        'percentual_sem_conflito': round(percentual_sem_conflito, 1),
        'conflitos_por_sala': conflitos_por_sala
    }


# ============================================================================
# VISUALIZAÇÕES (PROMPT 2)
# ============================================================================

def criar_grafico_ocupacao_salas(df_expandido: pd.DataFrame):
    """Gráfico de barras com ocupação por sala"""
    ocupacao = df_expandido['Sala'].value_counts().reset_index()
    ocupacao.columns = ['Sala', 'Ocorrências']
    
    fig = px.bar(
        ocupacao, 
        x='Sala', 
        y='Ocorrências',
        title='Ocupação por Sala (2026)',
        color='Ocorrências',
        color_continuous_scale='Blues'
    )
    fig.update_layout(showlegend=False)
    return fig


def criar_grafico_distribuicao_grupos(df_expandido: pd.DataFrame):
    """Gráfico de pizza com distribuição por grupo"""
    distribuicao = df_expandido['Grupo'].value_counts().head(10)
    
    fig = px.pie(
        values=distribuicao.values,
        names=distribuicao.index,
        title='Top 10 Grupos Mais Ativos'
    )
    return fig


def criar_timeline_ocupacao(df_expandido: pd.DataFrame):
    """Timeline de ocupação ao longo do ano"""
    df_expandido['Data Ocorrência'] = pd.to_datetime(df_expandido['Data Ocorrência'], dayfirst=True)
    df_expandido['Mês'] = df_expandido['Data Ocorrência'].dt.to_period('M').astype(str)
    
    ocupacao_mensal = df_expandido.groupby('Mês').size().reset_index(name='Reservas')
    
    fig = px.line(
        ocupacao_mensal,
        x='Mês',
        y='Reservas',
        title='Ocupação ao Longo de 2026',
        markers=True
    )
    fig.update_traces(line_color='#1f77b4', line_width=3)
    return fig




# ============================================================================
# INTERFACE PRINCIPAL
# ============================================================================

def main():
    # Sidebar
    with st.sidebar:
        # st.image("https://via.placeholder.com/200x80/1f77b4/ffffff?text=Igreja", use_column_width=True)
        st.title("⚙️ Configurações")
        
        # Input do Spreadsheet ID
        spreadsheet_id = st.text_input(
            "Google Spreadsheet ID",
            value=st.secrets.get("spreadsheet_id", ""),
            help="ID da planilha Google Sheets (parte da URL)"
        )
        
        worksheet_name = st.text_input(
            "Nome da Aba",
            value="Reservas",
            help="Nome da aba que contém os dados"
        )
        
        st.divider()
        
        # Botão de atualizar
        if st.button("🔄 Atualizar Dados", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        st.caption("💡 Dados atualizados automaticamente a cada 60 segundos")
    
    # Header principal
    st.title("🏛️ Sistema de Gestão de Reservas de Salas 2026")
    st.markdown("**Análise Completa de Conflitos e Sugestões**")
    
    # Carregar dados
    with st.spinner("📥 Carregando dados do Google Sheets..."):
    #     dfs_original = gsheet_service.load_all_data_gsheets(spreadsheet_id)
    
    # if not dfs_original:
    #     st.error("❌ Não foi possível carregar os dados. Verifique as configurações.")
    #     st.info("""
    #     **Como configurar:**
    #     1. Crie um Service Account no Google Cloud Console
    #     2. Compartilhe a planilha com o email do Service Account
    #     3. Adicione as credenciais no arquivo `.streamlit/secrets.toml`
        
    #     ```toml
    #     spreadsheet_id = "seu-spreadsheet-id"
        
    #     [gcp_service_account]
    #     type = "service_account"
    #     project_id = "seu-projeto"
    #     private_key_id = "..."
    #     private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
    #     client_email = "..."
    #     client_id = "..."
    #     ```
    #     """)
    #     return
    
    # df_reservas = dfs_original.get('Reservas', pd.DataFrame())
        df_reservas = gsheet_service.conn_gsheets(spreadsheet_id)
    if df_reservas.empty:
        st.error("❌ A aba 'Reservas' não foi encontrada ou está vazia.")
        return
    
    df_salas = pd.DataFrame() #dfs_original.get('Salas', pd.DataFrame()) 
    df_grupos = pd.DataFrame() #dfs_original.get('Grupos', pd.DataFrame())
    
    # Validar estrutura
    valido, erros = validar_estrutura_dados(df_reservas)
    if not valido:
        st.error("❌ Erro na estrutura dos dados:")
        for erro in erros:
            st.write(f"- {erro}")
        return
    
    # Processar dados
    with st.spinner("⚙️ Processando recorrências..."):
        df_expandido = expandir_recorrencias(df_reservas)
    
    with st.spinner("🔍 Detectando conflitos..."):
        conflitos = detectar_conflitos(df_expandido)
    
    with st.spinner("💡 Gerando sugestões..."):
        sugestoes = recommendation_service.generate_recommendations(df_expandido, conflitos)
    
    stats = calcular_estatisticas(df_reservas, df_expandido, conflitos, sugestoes)
    
    # Dashboard de Estatísticas
    st.header("📊 Estatísticas Gerais")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total de Ocorrências",
            f"{stats['total_ocorrencias']:,}",
            delta=f"{stats['total_reservas_originais']} reservas base"
        )
    
    with col2:
        st.metric(
            "Conflitos Detectados",
            stats['total_conflitos'],
            delta="Requer atenção" if stats['total_conflitos'] > 0 else "Tudo OK",
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            "Atividades c/ Opções",
            stats['atividades_com_opcoes'],
            delta=f"{stats['percentual_sem_conflito']}% sem conflito"
        )
    
    with col4:
        st.metric(
            "Salas Cadastradas",
            stats['total_salas'],
            delta=f"{stats['total_grupos']} grupos"
        )
    
    # Tabs principais
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Dashboard", 
        "⚠️ Conflitos", 
        "✅ Sugestões", 
        "📅 Calendário",
        "📋 Dados Brutos"
    ])
    
    # TAB 1: DASHBOARD
    with tab1:
        st.subheader("Visão Geral do Sistema")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(criar_grafico_ocupacao_salas(df_expandido), use_container_width=True)
        
        with col2:
            st.plotly_chart(criar_grafico_distribuicao_grupos(df_expandido), use_container_width=True)
        
        # st.plotly_chart(criar_timeline_ocupacao(df_expandido), use_container_width=True)
        
        # Sala com mais conflitos
        st.subheader("🎯 Insights")
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"""
            **Sala com Mais Conflitos:**  
            🏠 {stats['sala_mais_conflitos'][0]}  
            ⚠️ {stats['sala_mais_conflitos'][1]} conflitos
            """)
        
        with col2:
            st.success(f"""
            **Taxa de Sucesso:**  
            ✅ {stats['percentual_sem_conflito']}%  
            Opções sem conflito
            """)
    
    # TAB 2: CONFLITOS
    with tab2:
        # Cabeçalho com ícone e contagem
        st.subheader(f"⚠️ Conflitos Identificados ({len(conflitos)})")
        
        if not conflitos:
            # Layout de Sucesso (CheckCircle do React)
            container_sucesso = st.container(border=True)
            with container_sucesso:
                st.markdown("<h1 style='text-align: center;'>✅</h1>", unsafe_allow_html=True)
                st.markdown("<h3 style='text-align: center; color: #166534;'>Parabéns!</h3>", unsafe_allow_html=True)
                st.markdown("<p style='text-align: center; color: #666;'>Nenhum conflito encontrado</p>", unsafe_allow_html=True)
            return

        # --- ÁREA DE FILTROS ---
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            salas = sorted(list(set(c['sala'] for c in conflitos)))
            filtro_sala = st.selectbox("Filtrar por Sala", ["Todas"] + salas)
        with col_f2:
            filtro_data = st.date_input("Filtrar por Data", value=None, format="DD/MM/YYYY")

        # Filtros lógicos
        conflitos_filtrados = conflitos
        if filtro_sala != "Todas":
            conflitos_filtrados = [c for c in conflitos_filtrados if c['sala'] == filtro_sala]
        if filtro_data:
            data_str = filtro_data.strftime('%d/%m/%Y')
            conflitos_filtrados = [c for c in conflitos_filtrados if c['data'] == data_str]

        st.write(f"Mostrando **{len(conflitos_filtrados)}** conflitos")
        
        conflitos_filtrados = sorted(
            conflitos_filtrados, 
            key=lambda x: (datetime.strptime(x['data'], '%d/%m/%Y'))
        )
        
        # --- LISTAGEM DE CONFLITOS (CARD STYLE NATIVO) ---
        for idx, conf in enumerate(conflitos_filtrados, 1):
            # Usamos um container com borda para simular o "card"
            with st.container(border=True):
                # Cabeçalho do Card
                header_col1, header_col2 = st.columns([3, 1])
                with header_col1:
                    st.markdown(f"### 📍 {conf['sala']}")
                    st.caption(f"📅 Data: {conf['data']}",)
                with header_col2:
                    st.error(f"Conflito #{idx}")                            

                # Corpo do Card (As duas reservas lado a lado)
                res1_col, res2_col = st.columns(2)
                
                with res1_col:
                    st.markdown("**Reserva 1**")
                    # Usando o help ou info para destacar a área da reserva
                    with st.container():
                        st.info(f"""
                        **{conf['grupo1']}** *{conf['atividade1']}* 🕒 {conf['horario1']}  
                        👤 {conf['responsavel1']}
                        """)
                        salas_livres = recommendation_service.search_available_rooms(
                        df_expandido, 
                        conf['data'], 
                        conf['horario1'].split("-")[0], # Assumindo que você guardou os objetos de hora no dict
                        conf['horario1'].split("-")[1])

                        if salas_livres:
                            with st.success("💡 **Sugestão de Reoferecimento:**"):
                                st.markdown(f"As seguintes salas estão livres neste dia e horário:")
                                # Exibe as salas como "tags" usando st.write ou markdown
                                salas_formatadas = " · ".join([f"`{s}`" for s in salas_livres])
                                st.markdown(salas_formatadas)
                        else:
                            with st.warning("⚠️ **Atenção:** Não há outras salas disponíveis para este horário."):
                                st.markdown("Considere ajustar o horário ou entrar em contato com a administração.")
                        
                
                with res2_col:
                    st.markdown("**Reserva 2**")
                    with st.container():
                        # Usamos 'warning' para diferenciar a segunda reserva e criar o tom laranja
                        st.warning(f"""
                        **{conf['grupo2']}** *{conf['atividade2']}* 🕒 {conf['horario2']}  
                        👤 {conf['responsavel2']}
                        """)
                        salas_livres = recommendation_service.search_available_rooms(
                        df_expandido, 
                        conf['data'], 
                        conf['horario1'].split("-")[0], # Assumindo que você guardou os objetos de hora no dict
                        conf['horario1'].split("-")[1])

                        if salas_livres:
                            with st.success("💡 **Sugestão de Reoferecimento:**"):
                                st.markdown(f"As seguintes salas estão livres neste dia e horário:")
                                # Exibe as salas como "tags" usando st.write ou markdown
                                salas_formatadas = " · ".join([f"`{s}`" for s in salas_livres])
                                st.markdown(salas_formatadas)
                        else:
                            with st.warning("⚠️ **Atenção:** Não há outras salas disponíveis para este horário."):
                                st.markdown("Considere ajustar o horário ou entrar em contato com a administração.")
            
            st.write("") # Espaçamento entre cards
    
    # TAB 3: SUGESTÕES
    with tab3:
        st.subheader(f"✅ Sugestões de Salas ({len(sugestoes)})")
        
        if len(sugestoes) == 0:
            st.info("ℹ️ Nenhuma atividade com múltiplas opções encontrada.")
        else:
            # Filtros
            filtro_conflito = st.radio(
                "Filtrar por:",
                ["Todas", "Apenas sem conflito", "Apenas com conflito"],
                horizontal=True
            )
            
            sugestoes_filtradas = sugestoes
            if filtro_conflito == "Apenas sem conflito":
                sugestoes_filtradas = [s for s in sugestoes if s['conflitos'] == 0]
            elif filtro_conflito == "Apenas com conflito":
                sugestoes_filtradas = [s for s in sugestoes if s['conflitos'] > 0]
            
            st.write(f"**Mostrando {len(sugestoes_filtradas)} de {len(sugestoes)} sugestões**")
            
            # Listar sugestões
            for idx, sug in enumerate(sugestoes_filtradas, 1):
                cor = "🟢" if sug['conflitos'] == 0 else "🟡"
                with st.expander(f"{cor} {sug['atividade']} - {sug['grupo']}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"""
                        **Detalhes:**  
                        👥 **Grupo:** {sug['grupo']}  
                        📝 **Atividade:** {sug['atividade']}  
                        📅 **Data:** {sug['data']}  
                        👤 **Responsável:** {sug['responsavel']}
                        """)
                        
                        st.markdown(f"""
                        **Opções Disponíveis:**  
                        {sug['opcoes_disponiveis']}
                        """)
                    
                    with col2:
                        st.markdown(f"""
                        **Recomendação:**
                        """)
                        st.success(f"🏠 **{sug['sala_recomendada']}**")
                        st.info(f"💡 {sug['justificativa']}")
                        
                        if sug['conflitos'] > 0:
                            st.warning(f"⚠️ {sug['conflitos']} conflito(s)")
    
    # TAB 4: CALENDÁRIO
    with tab4:
        st.subheader("📅 Calendário de Reservas")
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            salas_unicas = sorted(df_expandido['Sala'].unique())
            filtro_sala_cal = st.selectbox("Filtrar por Sala", ["Todas"] + list(salas_unicas))
        
        with col2:
            grupos_unicos = sorted(df_expandido['Grupo'].unique())
            filtro_grupo_cal = st.selectbox("Filtrar por Grupo", ["Todos"] + list(grupos_unicos))
        
        with col3:
            # Filtro de mês
            meses = sorted(df_expandido['Data Ocorrência'].unique())
            if meses:
                mes_padrao = meses[0][3:5]  # YYYY-MM
                filtro_mes = st.selectbox("Filtrar por Mês", ["Todos"] + sorted(list(set([m[3:5] for m in meses]))))
        
        # Aplicar filtros
        df_filtrado = df_expandido.copy()
        
        if filtro_sala_cal != "Todas":
            df_filtrado = df_filtrado[df_filtrado['Sala'] == filtro_sala_cal]
        
        if filtro_grupo_cal != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Grupo'] == filtro_grupo_cal]
        
        if 'filtro_mes' in locals() and filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Data Ocorrência'].str.contains(f"/{filtro_mes}/")]
        
        # Busca textual
        busca = st.text_input("🔍 Buscar por atividade ou responsável", "")
        if busca:
            df_filtrado = df_filtrado[
                df_filtrado['Atividade'].str.contains(busca, case=False, na=False) |
                df_filtrado['Responsável'].str.contains(busca, case=False, na=False)
            ]
        
        st.write(f"**Mostrando {len(df_filtrado)} de {len(df_expandido)} reservas**")
        
        # Verificar conflitos para cada reserva
        def tem_conflito(row):
            return any(
                c['sala'] == row['Sala'] and c['data'] == row['Data Ocorrência']
                for c in conflitos
            )
        
        # Exibir reservas
        for idx, row in df_filtrado.head(100).iterrows():
            conflito_presente = tem_conflito(row)
            cor_borda = "🔴" if conflito_presente else "🟢"
            
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"""
                    {cor_borda} **{row['Atividade']}**  
                    👥 {row['Grupo']} • 👤 {row['Responsável']}
                    """)
                
                with col2:
                    hora_fim_calc = calcular_hora_fim(row['Hora Início'], row['Hora fim'])
                    st.markdown(f"""
                    🏠 **{row['Sala']}**  
                    📅 {row['Data Ocorrência']}  
                    ⏰ {row['Hora Início']} - {hora_fim_calc}
                    """)
                    if conflito_presente:
                        st.error("⚠️ Conflito")
                
                st.divider()
        
        if len(df_filtrado) > 100:
            st.info(f"ℹ️ Mostrando apenas as primeiras 100 reservas. Use os filtros para refinar.")
    
    # TAB 5: DADOS BRUTOS
    with tab5:
        st.subheader("📋 Dados Brutos")
        
        tab_dados1, tab_dados2, tab_dados3 = st.tabs([
            "Reservas Originais",
            "Ocorrências Expandidas",
            "Exportar"
        ])
        
        with tab_dados1:
            st.write(f"**{len(df_reservas)} reservas cadastradas**")
            st.dataframe(df_reservas, use_container_width=True, height=400)
        
        with tab_dados2:
            st.write(f"**{len(df_expandido)} ocorrências em 2026**")
            st.dataframe(df_expandido, use_container_width=True, height=400)
        
        with tab_dados3:
            st.write("**Exportar Dados**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_original = df_reservas.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Reservas Originais (CSV)",
                    csv_original,
                    "reservas_originais.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            with col2:
                csv_expandido = df_expandido.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Ocorrências 2026 (CSV)",
                    csv_expandido,
                    "ocorrencias_2026.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            with col3:
                # Exportar conflitos
                if conflitos:
                    df_conflitos = pd.DataFrame(conflitos)
                    csv_conflitos = df_conflitos.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Conflitos (CSV)",
                        csv_conflitos,
                        "conflitos.csv",
                        "text/csv",
                        use_container_width=True
                    )
    
    # Footer
    st.divider()
    st.caption("💡 Sistema de Gestão de Reservas de Salas 2026 • Dados atualizados automaticamente")


if __name__ == "__main__":
    main()
            